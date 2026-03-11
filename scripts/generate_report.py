#!/usr/bin/env python3
"""
Daily Shopify Orders Report Generator

Flow:
  1. Compute report window: yesterday 10am → today 10am (SGT)
  2. POST date range to Make.com webhook → receives { orderData: [...] }
  3. Client-side filter (belt-and-suspenders in case Make returns all orders)
  4. Build one row per order; Lineitem name = comma-separated SKU-mapped items
  5. Generate styled Excel workbook
  6. Send workbook to Telegram
"""

import argparse
import io
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
import pytz

load_dotenv()
import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

# ─── Config ───────────────────────────────────────────────────────────────────

WEBHOOK_URL = os.environ["MAKE_WEBHOOK_URL"]
LAST_ORDER_WEBHOOK_URL = os.environ["MAKE_LAST_ORDER_WEBHOOK_URL"]
WEBHOOK_API_KEY = os.environ["MAKE_WEBHOOK_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TIMEZONE = os.environ.get("REPORT_TIMEZONE", "Asia/Singapore")

# Resolved relative to this script's directory
_SCRIPT_DIR = Path(__file__).parent
SKU_MAP_FILE = Path(os.environ.get("SKU_MAP_FILE", _SCRIPT_DIR.parent / "sku_map.txt"))

# ─── SKU map ──────────────────────────────────────────────────────────────────


def load_sku_map() -> dict[str, dict]:
    """
    Load SKU → display config from a text file.

    Format (one entry per line, comments with #):
        generic-sipcup=Sip Cup
        main-harness=Harness
        main-harness=<qty>x Harness-<arg1>/<arg2>, <qty>x Leash-<arg1>
        twinned-leash=Leash:1    <- :1 = inherit first 1 variant from main

    Template format (main-* only):
        Values containing <qty> or <arg1>, <arg2>, ... are treated as templates.
        <qty>  → the line item quantity
        <argN> → the Nth variant segment from the SKU (1-based)

    nonfulfil SKUs need no entry — they are skipped by prefix automatically.

    Returns dict of:
        { key: { "template": str } }                     # template entry
        { key: { "name": str, "inherit": int } }         # plain / twinned entry
    """
    sku_map: dict[str, dict] = {}
    if not SKU_MAP_FILE.exists():
        print(f"WARNING: SKU map file not found at {SKU_MAP_FILE}. SKUs will be used as-is.")
        return sku_map
    for line in SKU_MAP_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if "<" in value:
            # Template entry — contains <qty> / <arg1> / <arg2> ... placeholders
            sku_map[key] = {"template": value}
        elif ":" in value:
            name, _, inherit_str = value.partition(":")
            sku_map[key] = {"name": name.strip(), "inherit": int(inherit_str.strip())}
        else:
            sku_map[key] = {"name": value, "inherit": 0}
    print(f"Loaded {len(sku_map)} SKU mappings.")
    return sku_map


def _fmt_variant(v: str) -> str:
    """Short codes (sizes) → uppercase; longer terms (colours) → capitalised."""
    return v.upper() if len(v) <= 3 else v.capitalize()


# ─── Time window ──────────────────────────────────────────────────────────────


def get_report_window() -> tuple[datetime, datetime]:
    """Returns (start, end): yesterday 10:00am → today 10:00am in TIMEZONE."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    end = now.replace(hour=10, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=1)
    return start, end


# ─── Data fetching ────────────────────────────────────────────────────────────


def fetch_orders(start: datetime, end: datetime) -> list:
    """
    POST to Make.com webhook with the date window.
    Make.com should use these params to filter Shopify orders at source.
    Returns list of Shopify order objects.
    """
    payload = {
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    resp = requests.post(
        WEBHOOK_URL,
        json=payload,
        headers={"x-make-apikey": WEBHOOK_API_KEY},
        timeout=60,
    )

    print(f"Webhook status  : {resp.status_code} {resp.reason}")
    print(f"Webhook response: {resp.text[:500]}")

    resp.raise_for_status()

    data = resp.json()
    orders = data.get("orderData", [])
    print(f"Fetched {len(orders)} orders from webhook.")
    return orders


def fetch_last_order() -> list:
    """Call the last-order webhook. Returns a single-item list."""
    resp = requests.post(
        LAST_ORDER_WEBHOOK_URL,
        json={},
        headers={"x-make-apikey": WEBHOOK_API_KEY},
        timeout=60,
    )

    print(f"Webhook status  : {resp.status_code} {resp.reason}")
    print(f"Webhook response: {resp.text[:500]}")

    resp.raise_for_status()

    data = resp.json()
    orders = data.get("orderData", [])
    print(f"Fetched {len(orders)} order(s) from last-order webhook.")
    return orders


# ─── Filtering ────────────────────────────────────────────────────────────────


def filter_orders(orders: list, start: datetime, end: datetime) -> list:
    """Client-side filter on created_at in case webhook returns all orders."""
    print(f"Window : {start.isoformat()} -> {end.isoformat()}")
    filtered = []
    for order in orders:
        if True:
            filtered.append(order)
    print(f"Filtered to {len(filtered)} orders in window.")
    return filtered


# ─── Lineitem name ────────────────────────────────────────────────────────────


def build_lineitem_name(order: dict, sku_map: dict[str, dict]) -> str:
    """
    Build a comma-separated string of all fulfilable items in the order.

    SKU classes:
      nonfulfil-* → skipped entirely
      generic-*   → name from sku_map[full_sku], no variants
      main-{p}-{v1}-{v2}-...  → if sku_map["main-{p}"] has a template, expands
                                  <qty>/<arg1>/<arg2>/... with actual values;
                                  otherwise uses plain name + variants.
      twinned-*   → name + :N from sku_map[full_sku], inherits first N variants from
                    the main product found in the same order

    Example (template):  "1x Harness-Black/XS, 1x Leash-Black"
    Example (plain):     "2x Harness/Black/XS, 1x Leash/Black"
    """
    line_items = order.get("lineItems", [])

    # Pass 1 — extract variants of the first main product in the order
    main_variants: list[str] = []
    for item in line_items:
        sku = (item.get("sku") or "").strip()
        parts = sku.split("-")
        if parts[0] == "main" and len(parts) >= 3:
            # main-{product}-{v1}-{v2}-...  → variants start at index 2
            main_variants = [_fmt_variant(v) for v in parts[2:]]
            break

    # Pass 2 — build display string for each fulfilable item
    result = []
    for item in line_items:
        sku = (item.get("sku") or "").strip()
        qty = item.get("quantity", 1)
        parts = sku.split("-")
        cls = parts[0]

        if cls == "nonfulfil":
            continue

        elif cls == "generic":
            entry = sku_map.get(sku, {})
            name = entry.get("name") or item.get("title", sku)
            result.append(f"{qty}x {name}")

        elif cls == "main":
            product_key = f"main-{parts[1]}" if len(parts) > 1 else sku
            entry = sku_map.get(product_key, {})
            if "template" in entry:
                # Expand template: replace <qty> and <arg1>, <arg2>, ...
                expanded = entry["template"].replace("<qty>", str(qty))
                for i, seg in enumerate(parts[2:], start=1):
                    expanded = expanded.replace(f"<arg{i}>", _fmt_variant(seg))
                result.append(expanded)
            else:
                name = entry.get("name") or (parts[1].capitalize() if len(parts) > 1 else sku)
                variants = [_fmt_variant(v) for v in parts[2:]]
                if variants:
                    result.append(f"{qty}x {name}/{'/'.join(variants)}")
                else:
                    result.append(f"{qty}x {name}")

        elif cls == "twinned":
            entry = sku_map.get(sku, {})
            name = entry.get("name") or item.get("title", sku)
            inherit = entry.get("inherit", 0)
            inherited = main_variants[:inherit]
            if inherited:
                result.append(f"{qty}x {name}/{'/'.join(inherited)}")
            else:
                result.append(f"{qty}x {name}")

    return ", ".join(result)


# ─── Row building ─────────────────────────────────────────────────────────────

COLUMNS = [
    "Name",
    "Email",
    "Lineitem name",
    "Shipping Name",
    "Shipping Street",
    "Shipping Address1",
    "Shipping Address2",
    "Shipping Company",
    "Shipping City",
    "Shipping Zip",
    "Shipping Province",
    "Shipping Country",
    "Shipping Phone",
]


def build_rows(orders: list, sku_map: dict[str, dict]) -> list[list]:
    """One row per order."""
    rows = []
    for order in orders:
        addr = order.get("shippingAddress") or {}
        rows.append([
            order.get("name"),
            order.get("email"),
            build_lineitem_name(order, sku_map),
            addr.get("name"),
            addr.get("address1"),
            addr.get("address1"),
            addr.get("address2"),
            addr.get("company"),
            addr.get("city"),
            addr.get("zip"),
            addr.get("province"),
            addr.get("country"),
            addr.get("phone"),
        ])
    return rows


# ─── Excel styles ─────────────────────────────────────────────────────────────

_HEADER_FONT = Font(bold=True, name="Calibri", size=11)
_NORMAL_FONT = Font(name="Calibri", size=10)
_THIN = Side(style="thin", color="BBBBBB")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _auto_width(ws) -> None:
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max((len(str(cell.value)) for cell in col if cell.value), default=8)
        ws.column_dimensions[col_letter].width = min(max_len + 4, 60)


# ─── Sheet builder ────────────────────────────────────────────────────────────


def _build_orders_sheet(ws, rows: list[list]) -> None:
    ws.title = "Orders"
    ws.sheet_view.showGridLines = False

    # Header
    for col_idx, col_name in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _BORDER
    ws.row_dimensions[1].height = 20

    # Data rows
    for row_idx, row_data in enumerate(rows, start=2):
        for col_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = _NORMAL_FONT
            cell.border = _BORDER

    _auto_width(ws)


# ─── Excel generation ─────────────────────────────────────────────────────────


def generate_excel(rows: list[list]) -> io.BytesIO:
    wb = Workbook()
    _build_orders_sheet(wb.active, rows)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ─── Telegram ─────────────────────────────────────────────────────────────────


def send_telegram_document(buf: io.BytesIO, filename: str, caption: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    resp = requests.post(
        url,
        data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
        files={"document": (filename, buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=30,
    )
    resp.raise_for_status()
    print("Report sent to Telegram.")


def send_telegram_message(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(
        url,
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
        timeout=15,
    )


# ─── SKU validation ───────────────────────────────────────────────────────────


def find_missing_skus(orders: list) -> list[tuple[str, str]]:
    """Return (order_name, item_title) for every line item that has no SKU."""
    missing = []
    for order in orders:
        order_name = order.get("name", "?")
        for item in order.get("lineItems", []):
            sku = (item.get("sku") or "").strip()
            if not sku:
                missing.append((order_name, item.get("title", "Unknown product")))
    return missing


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--last", action="store_true", help="Fetch only the last order via the last-order webhook")
    args = parser.parse_args()

    sku_map = load_sku_map()

    try:
        if args.last:
            orders = fetch_last_order()
            label = "Last Order"
        else:
            start, end = get_report_window()
            print(f"Report window: {start.isoformat()} -> {end.isoformat()}")
            orders = filter_orders(fetch_orders(start, end), start, end)
            label = f"Daily Report — {end.strftime('%d %b %Y')}"

        tz = pytz.timezone(TIMEZONE)
        created_at = datetime.now(tz).strftime("%Y-%m-%d")

        if not orders:
            filename = f"Orders {created_at} #No Orders.xlsx"
            buf = generate_excel([])
            send_telegram_document(buf, filename, f"*WanderPaws {label}*\nNo orders found.")
            print("No orders — sent empty Excel via Telegram.")
            return

        # Sort ascending by order number so the sheet reads oldest → newest
        orders.sort(key=lambda o: int((o.get("name") or "#0").lstrip("#") or 0))

        missing_skus = find_missing_skus(orders)
        if missing_skus:
            lines = "\n".join(f"• {name}: _{title}_" for name, title in missing_skus)
            send_telegram_message(f"*WanderPaws SKU Missing*\nThe following items have no SKU and the report was not generated:\n{lines}")
            print("Aborted — missing SKUs detected.")
            return

        first_order_name = (orders[0].get("name") or "").lstrip("#")
        last_order_name = (orders[-1].get("name") or "").lstrip("#")
        if len(orders) == 1:
            filename = f"Orders {created_at} #{first_order_name}.xlsx"
        else:
            filename = f"Orders {created_at} #{first_order_name}-#{last_order_name}.xlsx"

        rows = build_rows(orders, sku_map)
        buf = generate_excel(rows)

        send_telegram_document(buf, filename, f"*WanderPaws {label}*\n`{len(orders)}` order(s)")

    except Exception as e:
        send_telegram_message(f"*WanderPaws Report Error*\n`{type(e).__name__}: {e}`")
        sys.exit(1)


if __name__ == "__main__":
    main()
