# Setup guide — Amazon invoices → Tally (no coding)

This app runs on the internet for free. You upload the ZIP you download from
**Amazon Business → bulk invoice download**, and it gives you:
- a **Tally import file** (only for invoices you haven't done before), and
- a **searchable list** of every invoice it has ever processed.

It opens in any browser, including your **phone**. Setup is one-time (~20 min).
Follow the steps in order. You don't need to understand the code.

---

## What you'll create (all free)
1. A **GitHub** account — holds the app's code.
2. A **Supabase** project — the database (its "memory" of processed invoices).
3. A **Streamlit Community Cloud** account — runs the app and gives you the link.

---

## Step 1 — Put the code on GitHub
1. Go to **https://github.com** → **Sign up** (free). Verify your email.
2. Click the **+** (top-right) → **New repository**.
   - Repository name: `amazon-tally` (anything is fine).
   - Set it to **Private**.
   - Click **Create repository**.
3. On the new repo page, click **uploading an existing file**.
4. Drag in **all the files from the `invoice-tally-app` folder** I gave you:
   `app.py`, `db.py`, `invoice_parser.py`, `tally_export.py`, `requirements.txt`,
   the `.streamlit` folder (with `config.toml`), and this `SETUP.md`.
   - ⚠️ Do **NOT** upload any file named `secrets.toml`. Secrets go in Step 3, not in GitHub.
5. Click **Commit changes**.

---

## Step 2 — Create the database (Supabase) and copy its link
1. Go to **https://supabase.com** → **Start your project** → sign in with GitHub.
2. **New project**:
   - Name: `amazon-tally`
   - **Database password**: pick a strong one. **Use only letters and numbers**
     (avoid `@ # / : ?` — they complicate the link). Save it somewhere safe.
   - Region: pick the one closest to you (e.g. Mumbai/Singapore).
   - Click **Create new project** and wait ~2 minutes.
3. Get the connection link **that works on the free host**:
   - Click the green **Connect** button at the top of the Supabase dashboard.
   - Choose the **Session pooler** tab (under "Connection pooling").
   - Copy that **URI**. It looks like:
     ```
     postgresql://postgres.<your-ref>:YOUR-PASSWORD@aws-1-<region>.pooler.supabase.com:5432/postgres
     ```
   - Replace `YOUR-PASSWORD` with your database password.

   > ⚠️ **Do NOT use the "Direct connection" string** (the one that looks like
   > `...@db.xxxxx.supabase.co:5432`). It is IPv6-only and **will not connect** from
   > Streamlit Cloud. The **Session pooler** string (`...pooler.supabase.com`) is the
   > one that works. The app handles special characters in your password automatically.

You do **not** need to create any tables — the app makes them automatically the first time.

---

## Step 3 — Deploy the app (Streamlit) and paste the secrets
1. Go to **https://share.streamlit.io** → **Sign in with GitHub** → allow access.
2. Click **Create app** → **Deploy a public app from GitHub** (or "from a repo").
   - **Repository**: pick your `amazon-tally` repo.
   - **Branch**: `main`.
   - **Main file path**: `app.py`.
   - Click **Deploy**. Wait ~2–3 minutes for it to build.
3. **Add the secrets** (this is the password + database link, kept off GitHub):
   - Open your app → bottom-right **Manage app** (or the **⋮** menu) → **Settings → Secrets**.
   - Paste exactly this, with **your** values:
     ```
     APP_PASSWORD = "pick-a-strong-app-password"
     DB_URL = "postgresql://postgres:YOUR-PASSWORD@db.xxxxxxxx.supabase.co:5432/postgres"
     ```
   - Click **Save**. The app restarts.
4. Open the app link. It asks for the **APP_PASSWORD** you just set. Enter it — you're in.
   - Share the **link + the app password** only with people you trust. No password = no access.

---

## Step 4 — Set your Tally ledger names (one-time)
Tally only imports if the ledger names match your Tally company **exactly**.
1. In the app, open **Settings** (left menu).
2. Fill in, exactly as they appear in your Tally:
   - **Company name** (your Tally company)
   - **Voucher type** (usually `Purchase`)
   - **Purchase ledger** (e.g. `Purchase` or `Purchase 5%`)
   - **IGST / CGST / SGST ledgers** (e.g. `Input IGST`, `Input CGST`, `Input SGST`)
3. **Supplier → party ledger** (optional): the supplier on these invoices is
   `RETAILEZ PRIVATE LIMITED`. If your Tally has that creditor under a different
   name, add a mapping here. If not, leave it — the app uses the invoice name.
4. Click **Save settings**.

---

## Step 5 — Day-to-day use
1. On Amazon Business, download the **bulk invoice ZIP**.
2. In the app → **Upload & check** → choose the ZIP → **Process ZIP**.
3. You'll see a summary: **PDFs / New / Duplicates / Flagged**.
4. Click **Generate Tally XML** → **Download Tally XML**.
5. Click **✅ Mark as exported** so those invoices are remembered (never exported twice).
6. **Report** page lists everything ever processed; search it; export to CSV/Excel.

Re-uploading the same ZIP later produces **0 new** invoices — the memory prevents duplicates.

---

## Step 6 — Import the XML into Tally Prime
1. Open **Tally Prime** and load the **same company** you named in Settings.
2. **Gateway of Tally → Import → Vouchers** (in older Tally: *Import Data → Vouchers*).
3. Choose the **XML file** you downloaded. Set behaviour to **Add / Combine** as you prefer.
4. Import. Tally creates the Purchase vouchers.
   - If Tally reports "ledger not found", the name in **Settings** didn't match Tally —
     fix the name in Settings, re-generate, re-import. (Nothing bad happens; just rename.)

---

## Free-tier limits (and how to stay inside them)
- **App sleeps when idle** → first visit after a while takes ~20–30 sec to wake. Normal.
- **~1 GB memory** on the free host → if a **huge** ZIP fails, split it into a few
  smaller ZIPs and upload them one at a time. The app warns you when a ZIP is large.
- **Upload size**: set to 400 MB in the app's config. Keep ZIPs under that.
- **Supabase free**: ~500 MB database — each invoice is tiny, so that's hundreds of
  thousands of invoices. Supabase may pause a project after long inactivity; just open
  its dashboard to resume.
- It's a public link → that's why there's a **password**. Keep it private; rotate it
  (and the database password) occasionally in Supabase → Settings → Database.

---

## Scanned / image invoices
If an invoice PDF is a **scanned image** (no real text), the app can't read it and lists
it under **"could not read"** — it won't crash. Those need OCR, which this free version
doesn't do; download the normal (text) invoice from Amazon instead.
