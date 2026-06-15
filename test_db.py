"""
Live test against the real Supabase database (reads DB_URL from Streamlit secrets).
Creates the tables, does an insert/dedup/settings/mapping round-trip, then cleans
up the test rows. Run locally only; not part of the deployed app.
"""

import db

TK = ("__TEST_INV__", "00TESTGSTIN0000")

db.init_db()
print("tables ready")

db.run("DELETE FROM invoices WHERE invoice_number=%s", ("__TEST_INV__",))
assert not db.invoice_exists(*TK), "test row should not exist yet"

db.insert_invoice({
    "invoice_number": "__TEST_INV__", "supplier_gstin": "00TESTGSTIN0000",
    "supplier_name": "TEST", "invoice_date": "2026-06-02", "order_number": "x",
    "taxable": 100, "cgst": 0, "sgst": 0, "igst": 5, "tax_rate": "5%",
    "total": 105, "tax_type": "IGST", "irn": "x", "source_file": "t.pdf",
})
assert db.invoice_exists(*TK), "dedup should now find the row"
db.insert_invoice({"invoice_number": "__TEST_INV__", "supplier_gstin": "00TESTGSTIN0000",
                   "supplier_name": "TEST"})  # ON CONFLICT -> no duplicate
n = db.run("SELECT count(*) AS c FROM invoices WHERE invoice_number=%s",
           ("__TEST_INV__",), fetch="one")["c"]
assert n == 1, f"expected 1 row, got {n}"
print("insert + dedup OK (no duplicate on re-insert)")

db.save_settings({"__test_key__": "__test_val__"})
assert db.get_settings().get("__test_key__") == "__test_val__"
print("settings round-trip OK")

db.save_supplier_map("__TEST_SUP__", "Ledger X")
assert db.get_supplier_map().get("__TEST_SUP__") == "Ledger X"
print("supplier mapping OK")

# cleanup
db.run("DELETE FROM invoices WHERE invoice_number=%s", ("__TEST_INV__",))
db.run("DELETE FROM settings WHERE key=%s", ("__test_key__",))
db.delete_supplier_map("__TEST_SUP__")

print("\nDB ALL OK - real Supabase: connect, create tables, dedup, settings, mapping. Test rows removed.")
