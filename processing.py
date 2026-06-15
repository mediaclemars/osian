"""
processing.py — pure ZIP→invoices logic (no Streamlit), so it's testable and
memory-friendly. Reads ONE PDF at a time out of the (possibly huge, nested) ZIP.
"""

import io
import zipfile

from invoice_parser import extract_text, looks_like_tax_invoice, parse_invoice


def pdf_names(zip_bytes):
    """Open the zip and return (zipfile, [pdf member names anywhere inside])."""
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = [n for n in zf.namelist() if n.lower().endswith(".pdf") and not n.endswith("/")]
    return zf, names


def classify_zip(zip_bytes, exists_fn, on_progress=None):
    """
    Walk every PDF, identify invoices, dedup, extract.
    exists_fn(invoice_number, supplier_gstin) -> bool (DB duplicate check).
    on_progress(done, total) -> optional UI callback.
    Returns a result dict. Never raises on a single bad PDF.
    """
    zf, names = pdf_names(zip_bytes)
    total = len(names)
    res = {"total_pdfs": total, "new": [], "duplicates": [],
           "skipped": [], "flagged": [], "unreadable": []}
    seen = set()  # dedup within this run too

    for i, name in enumerate(names, start=1):
        fname = name.split("/")[-1]
        text = ""
        try:
            text = extract_text(zf.read(name))  # one PDF in memory at a time
        except Exception:
            text = ""
        try:
            if not text or len(text.strip()) < 30:
                res["unreadable"].append(fname)            # scanned/image -> needs OCR
            elif not looks_like_tax_invoice(text):
                res["skipped"].append(fname)               # not a GST invoice
            else:
                rec = parse_invoice(text, fname)
                key = (rec.get("invoice_number"), rec.get("supplier_gstin"))
                if not rec["reconciled"]:
                    res["flagged"].append(rec)
                elif key in seen or exists_fn(*key):
                    res["duplicates"].append(rec)
                else:
                    seen.add(key)
                    res["new"].append(rec)
        except Exception as e:                              # never stop on one bad PDF
            res["unreadable"].append(f"{fname} (error: {e})")
        if on_progress:
            on_progress(i, total)
    return res
