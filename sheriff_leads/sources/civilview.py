"""CivilView source: 17 NJ counties publish sheriff sales as HTML on
salesweb.civilview.com (Tyler Technologies "Sales Web"). Same pipeline, different
fetcher. No PDF involved.

Verified live against Monmouth County (countyId=8) on 2026-09-15:
  list:    GET /Sales/SalesSearch?countyId=<id>
           second <table> on the page, headings: '', Sheriff #, Status, Sales Date,
           Plaintiff, Defendant, Address. First cell is a "View Details" link.
  details: GET /Sales/SaleDetails?PropertyId=<id>
           needs the session cookie from the list page or it bounces to the home page.
           Fields are <div class="sale-detail-item"> with a label div and a value div:
           Sheriff #, Court Case #, Sales Date, Plaintiff, Defendant, Address (two lines),
           Description, Approx. Judgment*, Attorney, Parcel # ("Lot 5, Block 193 ...").
           Plus a status history table (Status, Date).
"""
import hashlib
import re
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://salesweb.civilview.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (sheriff-leads bot)"}
DETAIL_PAUSE = 0.5  # seconds between detail pages, be polite


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _list_table(soup: BeautifulSoup):
    """The results table is the one whose headings include 'Sheriff #'."""
    for t in soup.find_all("table"):
        heads = [_clean(th.get_text()).lower() for th in t.find_all("th")]
        if "sheriff #" in heads:  # exact: the outer wrapper table's caption also says "sheriff"
            return t, heads
    raise RuntimeError("No results table with a 'Sheriff #' heading. Page layout may have changed.")


def fetch(county: dict, raw_dir=None, limit: int | None = None) -> tuple[list[dict], str]:
    s = requests.Session()
    s.headers.update(HEADERS)
    url = f"{BASE}/Sales/SalesSearch?countyId={county['civilview_county_id']}"
    r = s.get(url, timeout=30)
    r.raise_for_status()
    digest = hashlib.sha256(r.content).hexdigest()
    soup = BeautifulSoup(r.text, "html.parser")

    table, headers = _list_table(soup)
    colmap = {k.lower(): v for k, v in county["columns"].items()}
    rows: list[dict] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        row = {}
        for i, td in enumerate(cells):
            if i < len(headers) and headers[i] in colmap:
                row[colmap[headers[i]]] = _clean(td.get_text())
        link = tr.find("a", href=True)
        if link:
            href = link["href"]
            row["_details_url"] = href if href.startswith("http") else BASE + href
        if row.get("case_number"):
            rows.append(row)
    if limit:
        rows = rows[:limit]

    for row in rows:
        d = row.pop("_details_url", None)
        if not d:
            continue
        try:
            row.update(_details(s, d))
        except Exception as e:  # keep going, note the miss
            row["_details_error"] = str(e)
        time.sleep(DETAIL_PAUSE)
    return rows, digest


def _details(s: requests.Session, url: str) -> dict:
    r = s.get(url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out: dict = {}
    for item in soup.select("div.sale-detail-item"):
        lab = item.select_one(".sale-detail-label")
        val = item.select_one(".sale-detail-value")
        if not (lab and val):
            continue
        label = _clean(lab.get_text()).rstrip(":").rstrip("*").strip().lower()
        if label == "address":
            lines = [_clean(x) for x in val.get_text("\n").split("\n") if _clean(x)]
            if lines:
                out["address"] = lines[0]
            if len(lines) > 1:
                # "Wall NJ 07719" -> city, zip
                m = re.match(r"(.*?)\s+NJ\s+(\d{5})", lines[1])
                if m:
                    out["city"], out["zip"] = m.group(1), m.group(2)
        elif label == "attorney":
            out["attorney"] = _clean(val.get_text())
        elif label == "parcel #":
            out["parcel"] = _clean(val.get_text())
        elif label == "court case #":
            out["court_case"] = _clean(val.get_text())
        elif label.startswith("approx. judgment"):
            out["judgment"] = _clean(val.get_text())
    # status history: first table with Status / Date headings
    hist = []
    for t in soup.find_all("table"):
        heads = [_clean(th.get_text()).lower() for th in t.find_all("th")]
        if heads[:2] == ["status", "date"]:
            for tr in t.find_all("tr")[1:]:
                tds = [_clean(td.get_text()) for td in tr.find_all("td")]
                if len(tds) >= 2:
                    hist.append(f"{tds[0]} {tds[1]}")
            break
    if hist:
        out["status_history"] = "; ".join(hist)
    return out
