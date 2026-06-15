"""
End-to-end test of the REAL binary pipeline:
  generate PDFs (fpdf2) -> zip them -> classify_zip -> pdfplumber -> parse.
Covers: a real tax invoice, the order-summary (skipped), an unreadable PDF.
"""

import io
import zipfile

from fpdf import FPDF
from processing import classify_zip


def make_pdf(lines):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    for ln in lines:
        pdf.cell(0, 5, ln, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


INVOICE = make_pdf([
    "Tax Invoice/Bill of Supply/Cash Memo",
    "(Original for Recipient)",
    "Order Number: 404-1234567-1234567 Invoice Number : TEST-001",
    "Order Date: 29.05.2026 Invoice Details : HR-TEST-1",
    "Invoice Date : 02.06.2026",
    "IRN: 0f16304418f83d6772d1f304c2a72657c00992254472481ee361f5f381fb7576",
    "1 YONEX ZR 100 ... HSN:95065910",
    "453.33 -18.13 18 7833.60 5% IGST 391.68 8225.28",
    "Sold By :",
    "TEST SUPPLIER PVT LTD",
    "Gurgaon, Haryana, 122413",
    "PAN No: AALCR3173P",
    "GST Registration No: 06AALCR3173P1ZR",
    "Billing Address :",
    "OSIAN SPORTS",
    "GST Registration No: 29AAJFO7029G1ZY",
    "TOTAL: 391.68 8225.28",
    "Amount in Words: Eight Thousand Two Hundred Twenty-five Point Two Eight only",
])

ORDER_SUMMARY = make_pdf([
    "Final Details for Order #404-1234567-1234567",
    "Order Total: 1,14,240.00",
    "Grand Total: 1,14,240.00",
    "Please note:this is not a GST invoice.",
])

UNREADABLE = make_pdf(["."])  # almost no text -> simulates a scanned/image PDF


def build_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # nested folders, like the real Amazon bulk download
        z.writestr("OrderDocs/sub1/TEST-001.pdf", INVOICE)
        z.writestr("OrderDocs/sub1/404-1234567-1234567.pdf", ORDER_SUMMARY)
        z.writestr("OrderDocs/sub2/scan.pdf", UNREADABLE)
        z.writestr("OrderDocs/readme.txt", b"not a pdf")
    return buf.getvalue()


def main():
    res = classify_zip(build_zip(), exists_fn=lambda *a: False)
    print("total_pdfs:", res["total_pdfs"])
    print("new       :", [r["invoice_number"] for r in res["new"]])
    print("skipped   :", res["skipped"])
    print("unreadable:", res["unreadable"])
    print("flagged   :", [r["flags"] for r in res["flagged"]])

    assert res["total_pdfs"] == 3, res["total_pdfs"]
    assert len(res["new"]) == 1, res["new"]
    inv = res["new"][0]
    assert inv["invoice_number"] == "TEST-001", inv
    assert inv["supplier_gstin"] == "06AALCR3173P1ZR", inv
    assert inv["supplier_name"] == "TEST SUPPLIER PVT LTD", inv
    assert inv["invoice_date"] == "2026-06-02", inv
    assert inv["tax_type"] == "IGST" and inv["igst"] == 391.68, inv
    assert inv["total"] == 8225.28 and inv["taxable"] == 7833.60, inv
    assert inv["reconciled"], inv["flags"]
    assert res["skipped"] == ["404-1234567-1234567.pdf"], res["skipped"]
    assert len(res["unreadable"]) == 1, res["unreadable"]

    # dedup: same zip again with exists_fn=True -> 0 new
    res2 = classify_zip(build_zip(), exists_fn=lambda *a: True)
    assert len(res2["new"]) == 0 and len(res2["duplicates"]) == 1, res2

    print("\nPIPELINE OK: real PDFs -> pdfplumber -> parse -> classify -> dedup all correct.")


if __name__ == "__main__":
    main()
