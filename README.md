# Sheriff sale leads

Watches county sheriff sale listings and pushes new ones into Follow Up Boss as leads.
Runs on a GitHub Actions schedule, twice a week. No server.

**What this is:** a proof of concept I built in one day for a real estate investor's brief.
The investor needed a weekly public-record PDF, whose link changes every week, turned into
CRM leads automatically. It's a plain Python pipeline with no AI calls, because the job
didn't need them. All the data in this repo is made up. Nothing here came from a client.

**Worth a look:**
- **Two source types behind one interface.** County pages that post a weekly PDF
  (`sources/pdf_source.py`, using pdfplumber with per-county column mapping) and the
  CivilView web table that 17 New Jersey counties share (`sources/civilview.py`). Adding a
  county means adding a block of config, not code.
- **Dedupe and status tracking.** It checks case numbers against its own memory and the CRM.
  A status change (scheduled, adjourned, cancelled) updates the existing lead and adds a note.
- **Nothing gets lost.** Anything the CRM rejects goes to a fallback CSV (or a Google Sheet)
  and is retried next run.
- **A demo mode anyone can run.** Actions > Run workflow > `demo` processes a sample PDF
  against a fake CRM, with no secrets needed. `reset` clears the memory for a clean demo.
- **Secrets only in GitHub Actions secrets.** None are in the code.

## How it runs

1. For each county in `sheriff_leads/config.yaml`, fetch the current sale list
   (a PDF link on the county page, or the CivilView web table).
2. Parse every listing: case number, sale date, status, defendant, address, lot and
   block, plaintiff, attorney.
3. Dedupe on case number against `sheriff_leads/data/seen.json` and Follow Up Boss.
4. New listings become FUB leads. Status changes update the existing lead and add a note.
5. Anything FUB rejects goes to `data/fallback.csv` (and a Google Sheet if configured)
   and is retried next run.
6. One summary email per run.

## Setup

1. Settings > Secrets and variables > Actions: add `FUB_API_KEY` (required),
   `GMAIL_USER` + `GMAIL_APP_PASSWORD` (for the summary email), optionally
   `FUB_SYSTEM_KEY`, `SHEET_ID`, `GOOGLE_SA_JSON`.
2. In Follow Up Boss, Admin > Custom Fields, create: Case Number, Sale Status, Plaintiff,
   Attorney, Lot Block, Sale Date, Defendant Raw, Court Case, Judgment.
3. Edit `sheriff_leads/config.yaml`: your counties, and `alerts.to`.
4. Actions > Sheriff sale leads > Run workflow. Pick `demo` to see it work on the sample
   file with no secrets, or `live` for the real thing.

## Adding a county

Copy a block in `config.yaml`. PDF counties need the page URL and a link pattern.
CivilView counties (17 in NJ) need only the `countyId` from the site URL.

## Running by hand

```
cd sheriff_leads
python -m pip install -r requirements.txt
python main.py --dry-run --county "Monmouth County" --limit 8
python main.py --pdf ../sample/sample_sale_list.pdf --county "Example County" --fake-fub
```
