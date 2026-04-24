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
  3. Map each line item SKU → display name (via scripts/sku_config.py)
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
├── scripts/sku_config.py    # Live SKU → display name mapping
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

## SKU mapping (`scripts/sku_config.py`)

Controls how Shopify SKUs appear in the report's **Lineitem name** column.

The live SKU mapping currently lives in `scripts/sku_config.py` as a Python dict named `SKU_MAP`.

Behaviour:
- known SKU with products → expands into report line items
- known SKU mapped to `[]` → skipped silently
- unknown SKU → raises `ValueError` and fails the run

Examples of skipped SKUs include `freewarranty`, `freepriorityshipping`, `nonfulfil-shipping`, and the `defaultleash-*` SKUs.
