"""
app.py — Amazon Business invoices -> Tally importer (Streamlit, mobile-friendly).
Password-gated. Reads secrets: APP_PASSWORD, DB_URL. Persists to Supabase Postgres.
"""

import io
import zipfile
import datetime as dt

import pandas as pd
import streamlit as st

import db
from processing import classify_zip
from tally_export import build_tally_xml

st.set_page_config(page_title="Amazon → Tally Invoices", page_icon="🧾", layout="centered")


# --------------------------------------------------------------- login gate ---
def require_login():
    if st.session_state.get("authed"):
        return True
    st.title("🧾 Amazon → Tally")
    st.caption("Private. Enter the password to continue.")
    if "APP_PASSWORD" not in st.secrets:
        st.error("APP_PASSWORD is not set in Streamlit secrets. Add it, then reload.")
        st.stop()
    with st.form("login"):
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Enter", use_container_width=True):
            if pw == st.secrets["APP_PASSWORD"]:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("Wrong password.")
    st.stop()


def ensure_db():
    if "DB_URL" not in st.secrets:
        st.error("DB_URL is not set in Streamlit secrets. Add your Supabase connection string.")
        st.stop()
    try:
        db.init_db()
    except Exception as e:
        st.error(f"Could not connect to the database. Check DB_URL in secrets.\n\n{e}")
        st.stop()


# ------------------------------------------------------------- zip handling ---
def process_zip(zip_bytes):
    """Walk PDFs (memory-friendly), identify invoices, dedup, extract."""
    try:
        bar = st.progress(0.0, text="Reading PDFs…")

        def on_progress(done, total):
            bar.progress(done / total if total else 1.0, text=f"{done} / {total} PDFs")

        res = classify_zip(zip_bytes, db.invoice_exists, on_progress)
        bar.empty()
        return res
    except zipfile.BadZipFile:
        st.error("That file isn't a valid ZIP. Upload the ZIP exactly as downloaded from Amazon.")
        return None


# ------------------------------------------------------------------- pages ---
def page_upload():
    st.header("⬆️ Upload & check invoices")
    st.caption("Upload the ZIP from Amazon Business → bulk invoice download. "
               "New invoices become a Tally file; duplicates are skipped automatically.")

    up = st.file_uploader("Choose the ZIP file", type=["zip"], accept_multiple_files=False)
    if up is not None:
        size_mb = up.size / (1024 * 1024)
        if size_mb > 180:
            st.warning(f"This ZIP is {size_mb:.0f} MB. On the free host that's near the limit — "
                       "if it fails, split it into smaller ZIPs and upload one at a time.")
        if st.button("Process ZIP", type="primary", use_container_width=True):
            with st.spinner("Reading PDFs…"):
                res = process_zip(up.getvalue())
            if res is not None:
                st.session_state["run"] = res
                st.session_state.pop("xml", None)
                st.session_state.pop("saved", None)

    res = st.session_state.get("run")
    if not res:
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PDFs", res["total_pdfs"])
    c2.metric("New", len(res["new"]))
    c3.metric("Duplicates", len(res["duplicates"]))
    c4.metric("Flagged", len(res["flagged"]))

    if res["new"]:
        st.subheader(f"🆕 {len(res['new'])} new invoice(s)")
        st.dataframe(_df(res["new"]), use_container_width=True, hide_index=True)

        # One click: build the Tally XML AND remember these invoices, so the same
        # ZIP won't ever be exported twice.
        if not st.session_state.get("saved"):
            if st.button("📥 Make Tally file & remember these invoices",
                         type="primary", use_container_width=True):
                settings = db.get_settings()
                st.session_state["xml"] = build_tally_xml(res["new"], settings, db.get_supplier_map())
                for rec in res["new"]:
                    db.insert_invoice(rec)
                st.session_state["saved"] = True
                st.rerun()
        else:
            st.success(f"✅ Saved {len(res['new'])} invoice(s) to memory — re-uploading the "
                       "same ZIP will now show them as duplicates (0 new).")

        if st.session_state.get("xml"):
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
            st.download_button("⬇️ Download Tally XML", st.session_state["xml"],
                               file_name=f"tally-purchase-{stamp}.xml",
                               mime="application/xml", use_container_width=True)
            st.caption("Import this file into Tally Prime: Gateway → Import → Vouchers.")

    if res["flagged"]:
        st.subheader(f"⚠️ {len(res['flagged'])} flagged for review (not exported)")
        rows = [{**_row(r), "reasons": "; ".join(r["flags"])} for r in res["flagged"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander(f"Duplicates skipped ({len(res['duplicates'])}) / "
                     f"non-invoices skipped ({len(res['skipped'])}) / "
                     f"unreadable ({len(res['unreadable'])})"):
        if res["duplicates"]:
            st.write("**Already processed (skipped):**")
            st.dataframe(_df(res["duplicates"]), use_container_width=True, hide_index=True)
        if res["skipped"]:
            st.write("**Not GST invoices (skipped):** " + ", ".join(res["skipped"]))
        if res["unreadable"]:
            st.write("**Could not read (likely scanned images — would need OCR):** "
                     + ", ".join(res["unreadable"]))


def page_report():
    st.header("📊 All processed invoices")
    rows = db.get_all_invoices()
    if not rows:
        st.info("Nothing processed yet. Upload a ZIP first.")
        return
    df = pd.DataFrame(rows)
    q = st.text_input("🔎 Search (invoice no, supplier, order, GSTIN)")
    if q:
        ql = q.lower()
        mask = df.apply(lambda r: ql in " ".join(str(v).lower() for v in r.values), axis=1)
        df = df[mask]
    st.caption(f"{len(df)} invoice(s)")
    st.dataframe(df, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    c1.download_button("⬇️ CSV", df.to_csv(index=False).encode("utf-8"),
                       "invoices.csv", "text/csv", use_container_width=True)
    xbuf = io.BytesIO()
    with pd.ExcelWriter(xbuf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Invoices")
    c2.download_button("⬇️ Excel", xbuf.getvalue(), "invoices.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)


def page_settings():
    st.header("⚙️ Tally settings")
    st.caption("These ledger names must match your Tally company EXACTLY, or the import fails.")
    s = db.get_settings()
    with st.form("settings"):
        company = st.text_input("Company name (in Tally)", s["company_name"])
        vtype = st.text_input("Voucher type", s["voucher_type"])
        purch = st.text_input("Purchase ledger", s["purchase_ledger"])
        igst = st.text_input("IGST ledger", s["igst_ledger"])
        cgst = st.text_input("CGST ledger", s["cgst_ledger"])
        sgst = st.text_input("SGST ledger", s["sgst_ledger"])
        if st.form_submit_button("Save settings", type="primary", use_container_width=True):
            db.save_settings({"company_name": company, "voucher_type": vtype,
                              "purchase_ledger": purch, "igst_ledger": igst,
                              "cgst_ledger": cgst, "sgst_ledger": sgst})
            st.success("Saved.")

    st.divider()
    st.subheader("Supplier → Tally party ledger (optional)")
    st.caption("By default the supplier name on the invoice is used as the party ledger. "
               "Map it here if your Tally ledger is named differently.")
    smap = db.get_supplier_map()
    if smap:
        st.dataframe(pd.DataFrame([{"Supplier (on invoice)": k, "Tally party ledger": v}
                                   for k, v in smap.items()]),
                     use_container_width=True, hide_index=True)
    with st.form("map"):
        c1, c2 = st.columns(2)
        sup = c1.text_input("Supplier name (exactly as on invoice)")
        led = c2.text_input("Tally party ledger name")
        if st.form_submit_button("Add / update mapping", use_container_width=True):
            if sup and led:
                db.save_supplier_map(sup.strip(), led.strip())
                st.success("Mapping saved.")
                st.rerun()


# --------------------------------------------------------------- helpers ---
def _row(r):
    return {"invoice_number": r.get("invoice_number"), "supplier_name": r.get("supplier_name"),
            "supplier_gstin": r.get("supplier_gstin"), "invoice_date": r.get("invoice_date"),
            "tax_type": r.get("tax_type"), "taxable": r.get("taxable"),
            "cgst": r.get("cgst"), "sgst": r.get("sgst"), "igst": r.get("igst"),
            "total": r.get("total"), "source_file": r.get("source_file")}


def _df(recs):
    return pd.DataFrame([_row(r) for r in recs])


# --------------------------------------------------------------- main ---
require_login()
ensure_db()

st.sidebar.title("🧾 Amazon → Tally")
page = st.sidebar.radio("Go to", ["Upload & check", "Report", "Settings"], label_visibility="collapsed")
st.sidebar.divider()
if st.sidebar.button("Log out", use_container_width=True):
    st.session_state.clear()
    st.rerun()

if page == "Upload & check":
    page_upload()
elif page == "Report":
    page_report()
else:
    page_settings()
