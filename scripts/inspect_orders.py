#!/usr/bin/env python3
"""
Read-only order inspection for WanderPaws.

Reuses the same Make.com webhook source as the fulfillment pipeline but avoids
all fulfillment side effects such as report generation, Telegram sends, and
reship injection.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
import pytz
import requests

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from sku_config import SKU_MAP  # noqa: E402

WEBHOOK_URL = os.environ["MAKE_WEBHOOK_URL"]
LAST_ORDER_WEBHOOK_URL = os.environ.get("MAKE_LAST_ORDER_WEBHOOK_URL")
WEBHOOK_API_KEY = os.environ["MAKE_WEBHOOK_API_KEY"]
TIMEZONE = os.environ.get("REPORT_TIMEZONE", "Asia/Singapore")


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect live order data without fulfillment side effects")
    parser.add_argument("--date", help="SGT date in YYYY-MM-DD; defaults to today")
    parser.add_argument("--limit", type=int, default=10, help="Max orders to emit after filtering/sorting")
    parser.add_argument("--order-numbers", help="Comma-separated order numbers like 1096,1097 or #1096,#1097")
    parser.add_argument("--last", action="store_true", help="Use the last-order webhook instead of the daily window")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser.parse_args()


def normalize_order_number(value: str) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits


def build_window(target_date: str | None) -> tuple[datetime, datetime]:
    tz = pytz.timezone(TIMEZONE)
    if target_date:
        day = tz.localize(datetime.strptime(target_date, "%Y-%m-%d"))
    else:
        now = datetime.now(tz)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    end = day.replace(hour=10, minute=0, second=0, microsecond=0)
    if not target_date and datetime.now(tz) < end:
        end = end - timedelta(days=0)
    start = end - timedelta(days=1)
    return start, end


def fetch_orders(start: datetime, end: datetime) -> list:
    payload = {"start": start.isoformat(), "end": end.isoformat()}
    resp = requests.post(
        WEBHOOK_URL,
        json=payload,
        headers={"x-make-apikey": WEBHOOK_API_KEY},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("orderData", [])


def fetch_last_order() -> list:
    if not LAST_ORDER_WEBHOOK_URL:
        raise RuntimeError("MAKE_LAST_ORDER_WEBHOOK_URL is not set")
    resp = requests.post(
        LAST_ORDER_WEBHOOK_URL,
        json={},
        headers={"x-make-apikey": WEBHOOK_API_KEY},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("orderData", [])


def select_orders(orders: list, limit: int, requested_numbers: set[str] | None) -> list:
    filtered = []
    for order in orders:
        order_name = order.get("name") or ""
        order_number = normalize_order_number(order_name)
        if requested_numbers and order_number not in requested_numbers:
            continue
        filtered.append(order)

    filtered.sort(key=lambda o: int(normalize_order_number(o.get("name") or "0") or 0), reverse=True)
    if limit > 0:
        filtered = filtered[:limit]
    return filtered


def build_lineitem_name(order: dict) -> str:
    slot_items: list[dict[str, int]] = []
    standalone_items: dict[str, int] = {}

    for item in order.get("lineItems", []):
        sku = (item.get("sku") or "").strip()
        qty = item.get("quantity", 1)

        if sku not in SKU_MAP:
            raise ValueError(f"Unknown SKU: {sku}")

        names = SKU_MAP[sku]
        if not names:
            continue

        if len(names) == 1:
            name = names[0]
            standalone_items[name] = standalone_items.get(name, 0) + qty
        else:
            while len(slot_items) < len(names):
                slot_items.append({})
            for i, name in enumerate(names):
                slot_items[i][name] = slot_items[i].get(name, 0) + qty

    parts = []
    for slot in slot_items:
        parts.extend(f"{total}x {name}" for name, total in slot.items())
    parts.extend(f"{total}x {name}" for name, total in standalone_items.items())
    return ", ".join(parts)


def serialize_order(order: dict) -> dict:
    shipping = order.get("shippingAddress") or {}
    line_items = []
    for item in order.get("lineItems", []):
        line_items.append({
            "title": item.get("title"),
            "sku": item.get("sku"),
            "quantity": item.get("quantity", 1),
            "product_legacy_id": item.get("product", {}).get("legacyResourceId"),
        })

    try:
        derived_lineitem_name = build_lineitem_name(order)
    except Exception as exc:
        derived_lineitem_name = f"ERROR: {exc}"

    return {
        "order_name": order.get("name"),
        "order_number": normalize_order_number(order.get("name") or ""),
        "created_at": order.get("createdAt") or order.get("created_at"),
        "email": order.get("email"),
        "shipping": {
            "name": shipping.get("name"),
            "address1": shipping.get("address1"),
            "address2": shipping.get("address2"),
            "company": shipping.get("company"),
            "city": shipping.get("city"),
            "zip": shipping.get("zip"),
            "province": shipping.get("province"),
            "country": shipping.get("country"),
            "phone": shipping.get("phone"),
        },
        "line_items": line_items,
        "derived_lineitem_name": derived_lineitem_name,
    }


def main():
    args = parse_args()
    requested_numbers = None
    if args.order_numbers:
        requested_numbers = {
            normalize_order_number(part)
            for part in args.order_numbers.split(",")
            if normalize_order_number(part)
        }

    if args.last:
        source_orders = fetch_last_order()
        mode = "last-order"
        window = None
    else:
        start, end = build_window(args.date)
        source_orders = fetch_orders(start, end)
        mode = "daily-window"
        window = {"start": start.isoformat(), "end": end.isoformat()}

    selected = select_orders(source_orders, args.limit, requested_numbers)
    output = {
        "mode": mode,
        "timezone": TIMEZONE,
        "window": window,
        "requested_order_numbers": sorted(requested_numbers) if requested_numbers else [],
        "returned_count": len(selected),
        "orders": [serialize_order(order) for order in selected],
    }

    if args.pretty:
        print(json.dumps(output, indent=2))
    else:
        print(json.dumps(output))


if __name__ == "__main__":
    main()
