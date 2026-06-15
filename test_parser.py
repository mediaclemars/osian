"""Validate the field extraction against the REAL sample invoice text layouts."""

from invoice_parser import looks_like_tax_invoice, parse_invoice

# --- Real text from the shared samples (pdfplumber-style text layer) ---

ORDER_SUMMARY = """Final Details for Order #404-5984987-6407514
Order Placed: 29 May 2026
Amazon.in order number: 404-5984987-6407514
Order Total: 1,14,240.00
Grand Total: 1,14,240.00
Please note:this is not a GST invoice.
"""

DEL5 = """Tax Invoice/Bill of Supply/Cash Memo
(Original for Recipient)
Order Number: 404-5984987-6407514 Invoice Number : DEL5-683907
Order Date: 29.05.2026 Invoice Details : HR-DEL5-1931441115-2627
Invoice Date : 02.06.2026
IRN:
0f16304418f83d6772d1f304c2a72657c00992254472481ee361f5f381fb7576
1 YONEX ZR 100 light ... B07QWSNTVY ( B07QWSNTVY )
HSN:95065910
₹453.33 -₹18.13 18 ₹7,833.60 5% IGST ₹391.68 ₹8,225.28
YONEX ZR 100 light ... B07QWSNTVY ( B07QWSNTVY )
HSN:95065910
₹453.33 -₹18.12 2 ₹870.42 5% IGST ₹43.52 ₹913.94
Sold By :
RETAILEZ PRIVATE LIMITED
*
Rect/Killa Nos. 38//8/2 min ... Gurgaon, Haryana, 122413
IN
PAN No: AALCR3173P
GST Registration No: 06AALCR3173P1ZR
Billing Address :
OSIAN SPORTS
Bengaluru Urban BENGALURU, KA, 560018
IN
GST Registration No: 29AAJFO7029G1ZY
State/UT Code: 29
Shipping Address :
OSIAN SPORTS
GST Registration No: 29AAJFO7029G1ZY
Place of supply: KA
TOTAL: ₹435.20 ₹9,139.22
Amount in Words:
Nine Thousand One Hundred Thirty-nine Point Two Two only
Whether tax is payable under reverse charge - No
"""

LKO1_539 = """Tax Invoice/Bill of Supply/Cash Memo
(Original for Recipient)
Order Number: 404-5984987-6407514 Invoice Number : LKO1-377539
Order Date: 29.05.2026 Invoice Details : UP-LKO1-1931441115-2627
Invoice Date : 02.06.2026
IRN:
4e274ed8a28aead55014b79ad366fc656a5c44b548df6202fa0321550083cd71
1 YONEX ZR 100 light ... B07QWSNTVY ( B07QWSNTVY )
HSN:95065910
₹453.33 -₹18.13 23 ₹10,009.60 5% IGST ₹500.48 ₹10,510.08
TOTAL: ₹500.48 ₹10,510.08
Amount in Words:
Ten Thousand Five Hundred Ten Point Zero Eight only
Sold By :
RETAILEZ PRIVATE LIMITED
*
Bhaukapur, Lucknow, Uttar Pradesh, 226401
IN
PAN No: AALCR3173P
GST Registration No: 09AALCR3173P1ZL
Billing Address :
OSIAN SPORTS
GST Registration No: 29AAJFO7029G1ZY
"""

LKO1_575 = """Tax Invoice/Bill of Supply/Cash Memo
Order Number: 404-5984987-6407514 Invoice Number : LKO1-377575
Order Date: 29.05.2026 Invoice Details : UP-LKO1-1931441115-2627
Invoice Date : 02.06.2026
IRN:
c775d18233f13c910853cc8dca23c31d8aec602775376b38f55e04771059b2c6
1 YONEX ... HSN:95065910
₹453.33 -₹18.14 2 ₹870.38 5% IGST ₹43.52 ₹913.90
YONEX ... HSN:95065910
₹453.33 -₹18.13 21 ₹9,139.20 5% IGST ₹456.96 ₹9,596.16
Sold By :
RETAILEZ PRIVATE LIMITED
PAN No: AALCR3173P
GST Registration No: 09AALCR3173P1ZL
Billing Address :
OSIAN SPORTS
GST Registration No: 29AAJFO7029G1ZY
TOTAL: ₹500.48 ₹10,510.06
Amount in Words:
Ten Thousand Five Hundred Ten Point Zero Six only
"""

SAMPLES = [("404-5984987-6407514.pdf", ORDER_SUMMARY),
           ("DEL5-683907.pdf", DEL5),
           ("LKO1-377539.pdf", LKO1_539),
           ("LKO1-377575.pdf", LKO1_575)]


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(f"{'File':22} {'Invoice#':14} {'SupplierGSTIN':17} {'Date':11} "
          f"{'Type':9} {'Taxable':>10} {'Tax':>9} {'Total':>11} Status")
    print("-" * 120)
    for fname, text in SAMPLES:
        if not looks_like_tax_invoice(text):
            print(f"{fname:22} {'-':14} {'-':17} {'-':11} {'-':9} "
                  f"{'-':>10} {'-':>9} {'-':>11} SKIPPED (not a GST invoice)")
            continue
        r = parse_invoice(text, fname)
        tax = round(r["igst"] + r["cgst"] + r["sgst"], 2)
        status = "OK" if r["reconciled"] else "FLAG: " + "; ".join(r["flags"])
        print(f"{fname:22} {r['invoice_number'] or '?':14} {r['supplier_gstin'] or '?':17} "
              f"{r['invoice_date'] or '?':11} {r['tax_type'] or '?':9} "
              f"{r['taxable']:>10} {tax:>9} {r['total']:>11} {status}")

    # assertions
    assert not looks_like_tax_invoice(ORDER_SUMMARY)
    d = parse_invoice(DEL5)
    assert d["invoice_number"] == "DEL5-683907", d["invoice_number"]
    assert d["supplier_gstin"] == "06AALCR3173P1ZR", d["supplier_gstin"]
    assert d["supplier_name"] == "RETAILEZ PRIVATE LIMITED", d["supplier_name"]
    assert d["invoice_date"] == "2026-06-02", d["invoice_date"]
    assert d["tax_type"] == "IGST" and d["igst"] == 435.20, d
    assert d["total"] == 9139.22 and d["taxable"] == 8704.02, d
    assert d["reconciled"], d["flags"]
    s = parse_invoice(LKO1_539)
    assert s["invoice_number"] == "LKO1-377539" and s["igst"] == 500.48 and s["total"] == 10510.08, s
    assert s["supplier_gstin"] == "09AALCR3173P1ZL" and s["reconciled"], s
    f = parse_invoice(LKO1_575)
    assert f["total"] == 10510.06 and f["taxable"] == 10009.58 and f["reconciled"], f
    print("\nALL ASSERTIONS PASSED - extraction matches the real samples.")


if __name__ == "__main__":
    main()
