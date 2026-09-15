"""Where rows go when FUB is down, plus a full mirror of every run.
CSV always. Google Sheet too if GOOGLE_SA_JSON and SHEET_ID are set."""
import csv
import json
import os
from pathlib import Path

FIELDS = ["run_at", "county", "case_number", "sale_date", "status", "first_name", "last_name",
          "defendant_raw", "street", "city", "zip", "lot", "block", "plaintiff", "attorney",
          "parcel_raw", "court_case", "judgment", "status_history", "fub_result"]


def append_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def append_sheet(rows: list[dict]) -> bool:
    """Returns True if written. Silently skips if Sheets is not configured."""
    sa, sheet_id = os.environ.get("GOOGLE_SA_JSON"), os.environ.get("SHEET_ID")
    if not (sa and sheet_id and rows):
        return False
    import gspread  # optional dependency
    gc = gspread.service_account_from_dict(json.loads(sa))
    ws = gc.open_by_key(sheet_id).sheet1
    if ws.row_count == 0 or not ws.row_values(1):
        ws.append_row(FIELDS)
    ws.append_rows([[r.get(k, "") for k in FIELDS] for r in rows])
    return True
