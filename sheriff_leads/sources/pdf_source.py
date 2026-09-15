"""PDF county source: find this week's PDF link on the page, download it, parse tables."""
import hashlib
import re
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (sheriff-leads bot; contact via email in repo)"}


def find_pdf_link(page_url: str, link_pattern: str) -> str:
    """Return the absolute URL of the first href matching link_pattern."""
    r = requests.get(page_url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    rx = re.compile(link_pattern)
    for a in soup.find_all("a", href=True):
        if rx.search(a["href"]) or rx.search(a.get_text(" ", strip=True)):
            return urljoin(page_url, a["href"])
    raise RuntimeError(f"No PDF link matching {link_pattern!r} on {page_url}")


def download(url: str, dest_dir: Path) -> tuple[Path, str]:
    """Download the PDF. Returns (path, sha256) so the caller can skip unchanged files."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    digest = hashlib.sha256(r.content).hexdigest()
    path = dest_dir / f"{digest[:12]}.pdf"
    path.write_bytes(r.content)
    return path, digest


def _clean(cell) -> str:
    if cell is None:
        return ""
    return re.sub(r"\s+", " ", str(cell)).strip()


def parse_tables(pdf_path: Path, columns: dict, table_strategy: str = "lines") -> list[dict]:
    """Read every table on every page. Map headings to standard names via `columns`.

    Rows with no case_number are treated as wrapped continuation lines and folded
    into the row above (addresses often wrap in county PDFs).
    """
    settings = {
        "vertical_strategy": table_strategy,
        "horizontal_strategy": table_strategy,
    }
    rows: list[dict] = []
    header_map: dict[int, str] | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables(settings):
                for raw in table:
                    cells = [_clean(c) for c in raw]
                    if not any(cells):
                        continue
                    # Header row: enough cells match the config column names
                    lowered = [c.lower() for c in cells]
                    hits = {i: columns[c] for i, c in enumerate(lowered) if c in columns}
                    if len(hits) >= 3:
                        header_map = hits
                        continue
                    if header_map is None:
                        continue  # text before the first header
                    row = {std: cells[i] if i < len(cells) else "" for i, std in header_map.items()}
                    if not row.get("case_number") and rows:
                        # continuation line: append text to the row above
                        for k, v in row.items():
                            if v:
                                rows[-1][k] = (rows[-1].get(k, "") + " " + v).strip()
                        continue
                    if row.get("case_number"):
                        rows.append(row)
    return rows


def fetch(county: dict, raw_dir: Path) -> tuple[list[dict], str]:
    """Full source run for one PDF county. Returns (rows, file_hash)."""
    url = find_pdf_link(county["page_url"], county["link_pattern"])
    path, digest = download(url, raw_dir / county["name"].replace(" ", "_"))
    rows = parse_tables(path, county["columns"], county.get("table_strategy", "lines"))
    return rows, digest
