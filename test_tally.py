"""Validate the Tally XML: well-formed + each voucher's debits == credits."""

import xml.dom.minidom as md
from tally_export import build_tally_xml

INVOICES = [
    {"invoice_number": "DEL5-683907", "supplier_name": "RETAILEZ PRIVATE LIMITED",
     "invoice_date": "2026-06-02", "order_number": "404-5984987-6407514",
     "taxable": 8704.02, "igst": 435.20, "cgst": 0, "sgst": 0,
     "total": 9139.22, "tax_type": "IGST"},
    # a synthetic intra-state (CGST+SGST) invoice to exercise that path
    {"invoice_number": "INV-CS-1", "supplier_name": "Acme Traders",
     "invoice_date": "2026-06-05", "order_number": "111-1",
     "taxable": 1000.0, "cgst": 90.0, "sgst": 90.0, "igst": 0,
     "total": 1180.0, "tax_type": "CGST/SGST"},
]
SETTINGS = {"company_name": "Osian Sports", "voucher_type": "Purchase",
            "purchase_ledger": "Purchase", "igst_ledger": "Input IGST",
            "cgst_ledger": "Input CGST", "sgst_ledger": "Input SGST"}

xml = build_tally_xml(INVOICES, SETTINGS, {"Acme Traders": "Acme Traders (Maharashtra)"})

dom = md.parseString(xml)  # raises if not well-formed
vouchers = dom.getElementsByTagName("VOUCHER")
assert len(vouchers) == 2, len(vouchers)

for v in vouchers:
    amts = [float(a.firstChild.data) for a in v.getElementsByTagName("AMOUNT")]
    assert abs(sum(amts)) < 0.01, ("voucher does not balance", sum(amts), amts)

# IGST voucher: party +9139.22, purchase -8704.02, igst -435.20
v1 = vouchers[0]
names = [n.firstChild.data for n in v1.getElementsByTagName("LEDGERNAME")]
assert "RETAILEZ PRIVATE LIMITED" in names and "Input IGST" in names and "Purchase" in names, names

# CGST/SGST voucher uses the mapped party ledger + both tax ledgers
v2 = vouchers[1]
names2 = [n.firstChild.data for n in v2.getElementsByTagName("LEDGERNAME")]
assert "Acme Traders (Maharashtra)" in names2, names2
assert "Input CGST" in names2 and "Input SGST" in names2, names2

# a missing supplier name must fall back to "Sundry Creditors" (never a blank ledger)
nv = build_tally_xml(
    [{"invoice_number": "X1", "invoice_date": "2026-06-02", "taxable": 100,
      "igst": 5, "cgst": 0, "sgst": 0, "total": 105, "tax_type": "IGST"}],
    SETTINGS, {})
assert "Sundry Creditors" in nv, "missing supplier name should fall back to Sundry Creditors"

print("Tally XML OK: well-formed, both vouchers balance, ledgers + supplier mapping + fallback correct.")
