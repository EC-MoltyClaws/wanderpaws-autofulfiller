# WanderPaws Autofulfiller

Automates the daily Shopify order fulfillment report for WanderPaws.

Every day it fetches yesterday's orders via a Make.com webhook, maps SKUs to human-readable names, builds a styled Excel file, and delivers it to a Telegram chat.

---

## How it works

```
Make.com webhook (Shopify orders)
        ↓
scripts/generate_report.py
  1. Compute window: yesterday 10am → today 10am (SGT)
  2. POST date range to Make.com → receives { orderData: [...] }
  3. Map each line item SKU → display name (via sku_map.txt)
  4. Build one row per order → styled Excel workbook
  5. Send workbook to Telegram
```

---

## Project structure

```
autofulfiller/
├── scripts/
│   ├── generate_report.py   # Main script — run this daily
│   └── test_webhook.py      # Dev utility — inspect raw webhook response
├── sku_map.txt              # SKU → display name configuration
├── main.py                  # Placeholder entry point
├── requirements.txt         # Python dependencies
└── .env                     # Secrets (not committed)
```

---

## Setup

**Prerequisites:** Python 3.13+

```bash
# Install dependencies
pip install -r requirements.txt
# or with uv:
uv sync
```

Copy the env template and fill in your secrets:

```bash
cp .env.example .env
```

### Required environment variables

| Variable | Description |
|---|---|
| `MAKE_WEBHOOK_URL` | Make.com webhook that returns all orders in a date window |
| `MAKE_LAST_ORDER_WEBHOOK_URL` | Make.com webhook that returns only the most recent order |
| `MAKE_WEBHOOK_API_KEY` | API key sent as `x-make-apikey` header |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Telegram chat/group ID to deliver the report |

### Optional environment variables

| Variable | Default | Description |
|---|---|---|
| `REPORT_TIMEZONE` | `Asia/Singapore` | Timezone for the 10am report window |
| `SKU_MAP_FILE` | `sku_map.txt` (repo root) | Path to the SKU mapping file |

---

## Running

```bash
# Daily report (yesterday 10am → today 10am)
python scripts/generate_report.py

# Fetch and report only the last order
python scripts/generate_report.py --last

# Test webhook connectivity and inspect raw response
python scripts/test_webhook.py
```

---

## SKU mapping (`sku_map.txt`)

Controls how Shopify SKUs appear in the report's **Lineitem name** column.

Three SKU types are supported:

### `generic-{sku}` — direct name
```
generic-sipcup=Sip Cup
```
The full SKU is the key; the value is the display name.

### `main-{product}` — template with variant expansion
```
main-harness=<qty>x Harness-<arg1>/<arg2>, <qty>x Leash-<arg1>
```
- `<qty>` is replaced with the line item quantity
- `<arg1>`, `<arg2>`, … are replaced with the variant segments from the SKU (in order)
- Example: SKU `main-harness-black-xs` qty 2 → `2x Harness-Black/XS, 2x Leash-Black`

### `twinned-{sku}` — inherits variants from the main product
```
twinned-leash=Leash:1
```
- `:N` means inherit the first N variant segments from the `main-*` product in the same order
- Example: if the order contains `main-harness-red-m`, `twinned-leash` qty 1 → `1x Leash/Red`

SKUs prefixed with `nonfulfil-` are silently skipped — no entry needed in the map.
