"""
tally_export.py — build a Tally Prime / ERP 9 import XML (Purchase vouchers).

Format: ENVELOPE > BODY > IMPORTDATA > REQUESTDATA > TALLYMESSAGE > VOUCHER.
Sign convention for a Purchase voucher:
  - Party (supplier) is CREDITED  -> ISDEEMEDPOSITIVE=No,  AMOUNT = +total
  - Purchase ledger is DEBITED    -> ISDEEMEDPOSITIVE=Yes, AMOUNT = -taxable
  - Tax ledgers are DEBITED       -> ISDEEMEDPOSITIVE=Yes, AMOUNT = -tax
Ledger names are taken from Settings (must match your Tally company EXACTLY).
"""

from xml.sax.saxutils import escape


def _amt(x):
    return f"{float(x or 0):.2f}"


def _date(iso):
    # "2026-06-02" -> "20260602"
    if not iso:
        return ""
    s = str(iso)[:10].replace("-", "")
    return s if len(s) == 8 else ""


def _ledger_entry(name, amount, is_debit):
    return (
        "          <ALLLEDGERENTRIES.LIST>\n"
        f"            <LEDGERNAME>{escape(name)}</LEDGERNAME>\n"
        f"            <ISDEEMEDPOSITIVE>{'Yes' if is_debit else 'No'}</ISDEEMEDPOSITIVE>\n"
        f"            <AMOUNT>{_amt(-amount if is_debit else amount)}</AMOUNT>\n"
        "          </ALLLEDGERENTRIES.LIST>\n"
    )


def build_voucher(inv, settings, supplier_map):
    name = inv.get("supplier_name")
    party = (supplier_map.get(name, name) if name else "Sundry Creditors")
    vtype = settings.get("voucher_type", "Purchase")
    date = _date(inv.get("invoice_date"))
    vno = inv.get("invoice_number") or ""

    entries = _ledger_entry(party, inv.get("total", 0), is_debit=False)
    entries += _ledger_entry(settings.get("purchase_ledger", "Purchase"), inv.get("taxable", 0), is_debit=True)
    if (inv.get("igst") or 0) > 0:
        entries += _ledger_entry(settings.get("igst_ledger", "Input IGST"), inv["igst"], is_debit=True)
    if (inv.get("cgst") or 0) > 0:
        entries += _ledger_entry(settings.get("cgst_ledger", "Input CGST"), inv["cgst"], is_debit=True)
    if (inv.get("sgst") or 0) > 0:
        entries += _ledger_entry(settings.get("sgst_ledger", "Input SGST"), inv["sgst"], is_debit=True)

    return (
        f'        <VOUCHER VCHTYPE="{escape(vtype)}" ACTION="Create" OBJVIEW="Invoice Voucher View">\n'
        f"          <DATE>{date}</DATE>\n"
        f"          <EFFECTIVEDATE>{date}</EFFECTIVEDATE>\n"
        f"          <VOUCHERTYPENAME>{escape(vtype)}</VOUCHERTYPENAME>\n"
        f"          <VOUCHERNUMBER>{escape(vno)}</VOUCHERNUMBER>\n"
        f"          <REFERENCE>{escape(vno)}</REFERENCE>\n"
        f"          <PARTYLEDGERNAME>{escape(party)}</PARTYLEDGERNAME>\n"
        f"          <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>\n"
        f"          <NARRATION>Amazon invoice {escape(vno)} (order {escape(inv.get('order_number') or '')})</NARRATION>\n"
        f"{entries}"
        "        </VOUCHER>\n"
    )


def build_tally_xml(invoices, settings, supplier_map):
    company = settings.get("company_name", "")
    vouchers = "".join(build_voucher(i, settings, supplier_map) for i in invoices)
    return (
        "<ENVELOPE>\n"
        "  <HEADER>\n"
        "    <TALLYREQUEST>Import Data</TALLYREQUEST>\n"
        "  </HEADER>\n"
        "  <BODY>\n"
        "    <IMPORTDATA>\n"
        "      <REQUESTDESC>\n"
        "        <REPORTNAME>Vouchers</REPORTNAME>\n"
        "        <STATICVARIABLES>\n"
        f"          <SVCURRENTCOMPANY>{escape(company)}</SVCURRENTCOMPANY>\n"
        "        </STATICVARIABLES>\n"
        "      </REQUESTDESC>\n"
        "      <REQUESTDATA>\n"
        '        <TALLYMESSAGE xmlns:UDF="TallyUDF">\n'
        f"{vouchers}"
        "        </TALLYMESSAGE>\n"
        "      </REQUESTDATA>\n"
        "    </IMPORTDATA>\n"
        "  </BODY>\n"
        "</ENVELOPE>\n"
    )
