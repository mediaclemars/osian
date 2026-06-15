# Amazon Business invoices → Tally

A free, password-protected web app (Streamlit) that turns the Amazon Business
**bulk invoice download ZIP** into a **Tally Prime** import file — automatically
**skipping invoices already processed** (memory stored in Supabase Postgres).
Opens in any browser, including a phone.

## 👉 Setup (no coding): see **[SETUP.md](SETUP.md)**
GitHub → Supabase → Streamlit Cloud → secrets → Tally ledgers → import. Step by step.

## What each file does
| File | Role |
|---|---|
| `app.py` | The web app: login, upload, export, report, settings |
| `invoice_parser.py` | Identify Amazon GST tax invoices + extract fields |
| `processing.py` | Walk every PDF in the (nested) ZIP, memory-friendly |
| `db.py` | Supabase Postgres: dedup memory, settings, supplier→ledger map |
| `tally_export.py` | Build the Tally purchase-voucher XML |
| `test_*.py` | Validate parser, Tally XML, the ZIP pipeline (run locally) |

Secrets (`APP_PASSWORD`, `DB_URL`) live only in Streamlit secrets — never in the code.
