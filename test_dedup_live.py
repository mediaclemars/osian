"""Live dedup test against the real Supabase DB (run locally with secrets)."""

import io
import zipfile
from fpdf import FPDF

import db
from processing import classify_zip


def make_pdf(lines):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Helvetica", size=10)
    for ln in lines:
        pdf.cell(0, 5, ln, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


INV = make_pdf([
    "Tax Invoice/Bill of Supply/Cash Memo",
    "Order Number: 404-9999999-9999999 Invoice Number : DEDUP-TEST-1",
    "Invoice Date : 02.06.2026",
    "1 Item HSN:95065910",
    "453.33 -18.13 18 7833.60 5% IGST 391.68 8225.28",
    "Sold By :", "DEDUP TEST SUPPLIER", "PAN No: AALCR3173P",
    "GST Registration No: 06AALCR3173P1ZR",
    "Billing Address :", "OSIAN SPORTS", "GST Registration No: 29AAJFO7029G1ZY",
    "TOTAL: 391.68 8225.28",
])


def zipbytes():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("a/b/DEDUP-TEST-1.pdf", INV)
    return b.getvalue()


db.init_db()
db.run("DELETE FROM invoices WHERE invoice_number=%s", ("DEDUP-TEST-1",))

r1 = classify_zip(zipbytes(), db.invoice_exists)
print("run1 -> new:", [x["invoice_number"] for x in r1["new"]],
      "| key:", (r1["new"][0]["invoice_number"], r1["new"][0]["supplier_gstin"]) if r1["new"] else None)
assert len(r1["new"]) == 1, r1

# simulate clicking "Mark as exported"
for rec in r1["new"]:
    db.insert_invoice(rec)
print("saved to DB (simulating Mark as exported)")
print("invoice_exists now? ->", db.invoice_exists("DEDUP-TEST-1", "06AALCR3173P1ZR"))

r2 = classify_zip(zipbytes(), db.invoice_exists)
print("run2 -> new:", [x["invoice_number"] for x in r2["new"]],
      "| duplicates:", len(r2["duplicates"]))

db.run("DELETE FROM invoices WHERE invoice_number=%s", ("DEDUP-TEST-1",))

assert len(r2["new"]) == 0 and len(r2["duplicates"]) == 1, ("DEDUP BUG", r2)
print("\nDEDUP WORKS: re-uploading the same invoice after saving -> 0 new, 1 duplicate.")
