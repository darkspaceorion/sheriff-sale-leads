# Sheriff sale leads

Watches county sheriff sale listings and pushes new ones into Follow Up Boss as leads.
Runs on a GitHub Actions schedule, twice a week. No server.

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
