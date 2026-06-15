"""
invoice_parser.py
Identify Amazon Business India GST tax invoices and extract their fields.

Built against REAL sample invoices (RetailEZ / Osian Sports, 2026):
  - Real invoices start with "Tax Invoice/Bill of Supply/Cash Memo".
  - The order-summary PDF says "this is not a GST invoice" -> skipped.
  - Labelled fields ("Invoice Number :", "Invoice Date :", "Sold By :", "PAN No:",
    "GST Registration No:") are extracted by label, so line ordering doesn't matter.
  - Totals come from the "TOTAL:" row: <total tax> <grand total>.
  - Tax split: IGST -> all in IGST; CGST/SGST -> half each (CGST==SGST by GST law).
The PDF->text step uses pdfplumber; everything below works on that text, so the
same logic is unit-tested directly against the sample text.
"""

import re
from collections import Counter
from datetime import date

GSTIN_RE = r"\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]"
PAN_RE = r"[A-Z]{5}[0-9]{4}[A-Z]"
AMOUNT_RE = r"-?\s*₹?\s*([0-9][0-9,]*\.\d{2})"


def extract_text(file_bytes):
    """Return the full text of a PDF (all pages). Empty string if unreadable."""
    import pdfplumber
    import io

    out = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out)


def looks_like_tax_invoice(text):
    """True only for real GST tax invoices (not order summaries / shipping docs)."""
    t = text or ""
    if "this is not a GST invoice" in t:
        return False
    if "Final Details for Order" in t and "Tax Invoice" not in t:
        return False
    return "Tax Invoice/Bill of Supply/Cash Memo" in t or (
        "Tax Invoice" in t and re.search(r"Invoice Number\s*:", t) is not None
    )


def _num(s):
    if s is None:
        return None
    s = str(s).replace("₹", "").replace(",", "").replace(" ", "").strip()
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _first(pattern, text, flags=re.IGNORECASE):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _normalize_date(d):
    """02.06.2026 / 02-06-2026 / 02/06/2026 -> 2026-06-02 (ISO). None if invalid."""
    if not d:
        return None
    m = re.match(r"(\d{2})[.\-/](\d{2})[.\-/](\d{4})", d.strip())
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    try:
        return date(int(yyyy), int(mm), int(dd)).isoformat()  # rejects month 13, day 32, etc.
    except ValueError:
        return None


def _supplier_gstin(text):
    """
    Seller GSTIN, found in a layout-proof way (the two-column PDF can interleave
    'Sold By' and 'Billing Address' text, so we don't rely on position):
      1) the GSTIN that CONTAINS the seller PAN (a GSTIN embeds its PAN) — exact link;
      2) else the GST Reg right after 'PAN No:';
      3) else the GSTIN appearing fewest times (buyer repeats in billing+shipping).
    """
    pan = _first(r"PAN No\s*:\s*(" + PAN_RE + r")", text)
    if pan:
        m = re.search(r"(\d{2}" + re.escape(pan) + r"[0-9A-Z]Z[0-9A-Z])", text)
        if m:
            return m.group(1)
    m = re.search(r"PAN No\s*:\s*[A-Z0-9]+\s*GST Registration No\s*:\s*(" + GSTIN_RE + r")",
                  text, re.IGNORECASE)
    if m:
        return m.group(1)
    gstins = re.findall(GSTIN_RE, text)
    if gstins:
        counts = Counter(gstins)
        return min(gstins, key=lambda g: (counts[g], gstins.index(g)))
    return None


def _buyer_gstin(text, supplier):
    for g in re.findall(GSTIN_RE, text):
        if g != supplier:
            return g
    return None


def _supplier_name(text):
    """
    Seller name, layout-proof: prefer the full-width 'For <NAME>: Authorized
    Signatory' line (never interleaves); else the line after 'Sold By :', guarding
    against accidentally grabbing the 'Billing Address' header.
    """
    m = re.search(r"For\s+([A-Z][A-Za-z0-9 &.\-]+?)\s*:\s*(?:\n\s*)?Authorized Signatory", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"Sold By\s*:\s*\n?\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        name = m.group(1).strip().rstrip("*").strip()
        if name and "Billing" not in name and "Address" not in name and "GST" not in name:
            return name
    return None


def _totals(text):
    """Return (total_tax, grand_total) from the last 'TOTAL:' row."""
    matches = list(re.finditer(r"TOTAL\s*:\s*((?:" + AMOUNT_RE + r"\s*){1,4})", text, re.IGNORECASE))
    if not matches:
        return None, None
    seg = matches[-1].group(1)
    nums = [_num(x) for x in re.findall(AMOUNT_RE, seg)]
    nums = [n for n in nums if n is not None]
    if len(nums) >= 2:
        return nums[-2], nums[-1]   # <total tax> <grand total>
    if len(nums) == 1:
        return None, nums[-1]
    return None, None


def _line_items(text):
    """Best-effort parse of item rows for cross-checking. Returns list of dicts."""
    row = re.compile(
        AMOUNT_RE + r"\s+-?\s*₹?\s*[0-9][0-9,]*\.\d{2}\s+(\d+)\s+" + AMOUNT_RE +
        r"\s+(\d+)%\s+(IGST|CGST|SGST)\s+" + AMOUNT_RE + r"\s+" + AMOUNT_RE,
        re.IGNORECASE,
    )
    items = []
    for m in row.finditer(text):
        items.append({
            "qty": int(m.group(2)),
            "net": _num(m.group(3)),
            "rate": m.group(4) + "%",
            "type": m.group(5).upper(),
            "tax": _num(m.group(6)),
            "total": _num(m.group(7)),
        })
    return items


def parse_invoice(text, source_file=""):
    """Extract all fields + reconciliation flags from one invoice's text."""
    raw_date = _first(r"Invoice Date\s*:\s*([\d./\-]{8,10})", text)
    rec = {
        "source_file": source_file,
        "invoice_number": _first(r"Invoice Number\s*:\s*([A-Z0-9][A-Z0-9\-]+)", text),
        "invoice_date": _normalize_date(raw_date),
        "order_number": _first(r"Order Number\s*:\s*([0-9\-]+)", text),
        "supplier_name": _supplier_name(text),
        "supplier_gstin": None,
        "buyer_gstin": None,
        "irn": _first(r"IRN\s*:\s*\n?\s*([0-9a-f]{40,})", text),
        "taxable": None, "cgst": 0.0, "sgst": 0.0, "igst": 0.0,
        "tax_rate": None, "total": None, "tax_type": None,
        "reconciled": False, "flags": [],
    }
    rec["supplier_gstin"] = _supplier_gstin(text)
    rec["buyer_gstin"] = _buyer_gstin(text, rec["supplier_gstin"])

    total_tax, grand_total = _totals(text)
    items = _line_items(text)
    flags = []

    if grand_total is None or total_tax is None:
        flags.append("could not read TOTAL row")
    else:
        rec["total"] = grand_total
        rec["taxable"] = round(grand_total - total_tax, 2)

        # tax type / split
        types = {it["type"] for it in items}
        if not types:
            if re.search(r"\bIGST\b", text):
                types = {"IGST"}
            elif re.search(r"\bCGST\b", text) or re.search(r"\bSGST\b", text):
                types = {"CGST", "SGST"}
        if "IGST" in types:
            rec["tax_type"] = "IGST"
            rec["igst"] = total_tax
        elif "CGST" in types or "SGST" in types:
            rec["tax_type"] = "CGST/SGST"
            rec["cgst"] = round(total_tax / 2, 2)
            rec["sgst"] = round(total_tax - rec["cgst"], 2)
        else:
            flags.append("tax type not found")

        rates = sorted({it["rate"] for it in items})
        if rates:
            rec["tax_rate"] = ", ".join(rates)
        elif re.search(r"(\d+)%", text):
            rec["tax_rate"] = re.search(r"(\d+%)", text).group(1)

        # cross-check totals against line items when available
        if items:
            net_sum = round(sum(i["net"] for i in items if i["net"] is not None), 2)
            tot_sum = round(sum(i["total"] for i in items if i["total"] is not None), 2)
            if abs(net_sum - rec["taxable"]) > 1.0:
                flags.append(f"taxable mismatch (items {net_sum} vs {rec['taxable']})")
            if abs(tot_sum - grand_total) > 1.0:
                flags.append(f"total mismatch (items {tot_sum} vs {grand_total})")

    if not rec["invoice_number"]:
        flags.append("invoice number not found")
    if not rec["supplier_gstin"]:
        flags.append("supplier GSTIN not found")
    if raw_date and not rec["invoice_date"]:
        flags.append("invalid invoice date")

    rec["flags"] = flags
    rec["reconciled"] = len(flags) == 0
    return rec
