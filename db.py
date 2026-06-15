"""
db.py — Supabase Postgres persistence (dedup memory + settings).
The connection string lives ONLY in Streamlit secrets (st.secrets["DB_URL"]),
never in code. Tables are created automatically on first run.
"""

import re
import psycopg2
import psycopg2.extras
import streamlit as st

# ---- default Tally settings (editable on the Settings page) ----
DEFAULT_SETTINGS = {
    "company_name": "",
    "voucher_type": "Purchase",
    "purchase_ledger": "Purchase",
    "cgst_ledger": "Input CGST",
    "sgst_ledger": "Input SGST",
    "igst_ledger": "Input IGST",
}


def _parse_db_url(url):
    """Tolerant parse that survives special chars (@, #) in the password."""
    m = re.match(
        r"postgres(?:ql)?://(?P<user>[^:]+):(?P<pwd>.+)@(?P<host>[^@:/]+):(?P<port>\d+)/(?P<db>[^?]+)",
        url.strip(),
    )
    if not m:
        raise ValueError(
            "DB_URL must look like postgresql://user:password@host:5432/postgres"
        )
    return m.groupdict()


@st.cache_resource(show_spinner=False)
def get_conn():
    p = _parse_db_url(st.secrets["DB_URL"])
    conn = psycopg2.connect(
        host=p["host"], port=p["port"], user=p["user"],
        password=p["pwd"], dbname=p["db"], sslmode="require",
        connect_timeout=15,
    )
    conn.autocommit = True
    return conn


def run(sql, params=(), fetch=None):
    """Execute SQL, reconnecting once if the cached connection went stale."""
    for attempt in (1, 2):
        try:
            conn = get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
                return None
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            if attempt == 2:
                raise
            get_conn.clear()


def init_db():
    run("""
        CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            invoice_number TEXT NOT NULL,
            supplier_gstin TEXT,
            supplier_name TEXT,
            invoice_date DATE,
            order_number TEXT,
            taxable NUMERIC, cgst NUMERIC, sgst NUMERIC, igst NUMERIC,
            tax_rate TEXT, total NUMERIC, tax_type TEXT,
            irn TEXT, source_file TEXT,
            processed_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (invoice_number, supplier_gstin)
        );
    """)
    run("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);")
    run("CREATE TABLE IF NOT EXISTS supplier_map (supplier_name TEXT PRIMARY KEY, party_ledger TEXT);")


# ---- dedup ----
def invoice_exists(invoice_number, supplier_gstin):
    row = run(
        "SELECT 1 FROM invoices WHERE invoice_number=%s AND COALESCE(supplier_gstin,'')=COALESCE(%s,'') LIMIT 1",
        (invoice_number, supplier_gstin), fetch="one",
    )
    return row is not None


def insert_invoice(r):
    run("""
        INSERT INTO invoices
          (invoice_number, supplier_gstin, supplier_name, invoice_date, order_number,
           taxable, cgst, sgst, igst, tax_rate, total, tax_type, irn, source_file)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (invoice_number, supplier_gstin) DO NOTHING
    """, (
        r.get("invoice_number"), r.get("supplier_gstin"), r.get("supplier_name"),
        r.get("invoice_date"), r.get("order_number"), r.get("taxable"),
        r.get("cgst"), r.get("sgst"), r.get("igst"), r.get("tax_rate"),
        r.get("total"), r.get("tax_type"), r.get("irn"), r.get("source_file"),
    ))


def get_all_invoices():
    return run("SELECT * FROM invoices ORDER BY processed_at DESC", fetch="all") or []


# ---- settings ----
def get_settings():
    rows = run("SELECT key, value FROM settings", fetch="all") or []
    s = dict(DEFAULT_SETTINGS)
    for row in rows:
        s[row["key"]] = row["value"]
    return s


def save_settings(d):
    for k, v in d.items():
        run("""INSERT INTO settings (key, value) VALUES (%s,%s)
               ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value""", (k, v))


# ---- supplier -> Tally party-ledger mapping ----
def get_supplier_map():
    rows = run("SELECT supplier_name, party_ledger FROM supplier_map", fetch="all") or []
    return {r["supplier_name"]: r["party_ledger"] for r in rows}


def save_supplier_map(supplier_name, party_ledger):
    run("""INSERT INTO supplier_map (supplier_name, party_ledger) VALUES (%s,%s)
           ON CONFLICT (supplier_name) DO UPDATE SET party_ledger=EXCLUDED.party_ledger""",
        (supplier_name, party_ledger))


def delete_supplier_map(supplier_name):
    run("DELETE FROM supplier_map WHERE supplier_name=%s", (supplier_name,))
