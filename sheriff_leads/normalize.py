"""Turn raw source rows into clean lead dicts. Same output shape for every county."""
import re

STATUS_WORDS = {
    "adjourn": "Adjourned",
    "cancel": "Cancelled",
    "sold": "Sold",
    "settle": "Settled",
    "bankrupt": "Bankruptcy",
    "sched": "Scheduled",
    "open": "Scheduled",
}

ZIP_RX = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
# values must start with a digit so "Lot and Block: Lot 5, Block 193" gives 5 / 193
LOT_BLOCK_RX = re.compile(r"(?i)lot(?:\(s\))?\s*(?:no\.?)?\s*:?\s*#?\s*(\d[\w.\-/]*).*?block(?:\(s\))?\s*(?:no\.?)?\s*:?\s*#?\s*(\d[\w.\-/]*)")
# "et al", "et. al.", "AKA", "a/k/a", "and", "&", ";" all end the first named party
PARTY_SPLIT_RX = re.compile(r"(?i)\s*(?:;|,?\s+\bet\.?\s*al\b\.?|\s+\band\b|\s+&\s+|\s+\ba/?k/?a\b|\s+\bet\s+ux\b)")


def split_address(addr: str, city: str = "", zip_code: str = "") -> tuple[str, str, str]:
    """'12 Main St, Freehold, NJ 07728' -> ('12 Main St', 'Freehold', '07728').
    If city/zip came in their own columns, keep them."""
    addr = addr or ""
    if not zip_code:
        m = ZIP_RX.search(addr)
        if m:
            zip_code = m.group(1)
            addr = addr[: m.start()].strip(" ,")
    addr = re.sub(r",?\s*NJ\s*$", "", addr, flags=re.I).strip(" ,")
    if not city and "," in addr:
        street, city = [p.strip() for p in addr.rsplit(",", 1)]
        addr = street
    return addr, city, zip_code


def split_defendant(raw: str) -> tuple[str, str]:
    """First named person -> (first, last). LLCs and estates keep the whole string as last."""
    raw = (raw or "").strip()
    first_party = PARTY_SPLIT_RX.split(raw)[0].strip(" ,;.")
    if re.search(r"(?i)\b(llc|inc|corp|estate|trust|bank|association|township|borough|city of)\b", first_party) or not first_party:
        return "", first_party or raw
    if "," in first_party:  # "SMITH, JOHN"
        last, first = [p.strip() for p in first_party.split(",", 1)]
        first = first.split()[0] if first else ""
        return first.title(), last.title()
    parts = first_party.split()  # "JOHN A SMITH" / "Ola Wayne Johnson"
    if len(parts) == 1:
        return "", parts[0].title()
    return parts[0].title(), parts[-1].title().rstrip(".,;")


def norm_status(s: str) -> str:
    s = (s or "").lower()
    for key, label in STATUS_WORDS.items():
        if key in s:
            return label
    return s.title() if s else "Unknown"


def normalize(row: dict, county: dict) -> dict:
    lot, block = row.get("lot", ""), row.get("block", "")
    if not (lot and block):
        m = LOT_BLOCK_RX.search(row.get("parcel", "") or " ".join(str(v) for v in row.values()))
        if m:
            lot, block = m.group(1), m.group(2)
    street, city, zip_code = split_address(row.get("address", ""), row.get("city", ""), row.get("zip", ""))
    first, last = split_defendant(row.get("defendant", ""))
    return {
        "county": county["name"],
        "state": county.get("state", "NJ"),
        "case_number": re.sub(r"\s+", "", row.get("case_number", "")).upper(),
        "sale_date": row.get("sale_date", ""),
        "plaintiff": row.get("plaintiff", ""),
        "defendant_raw": row.get("defendant", ""),
        "first_name": first,
        "last_name": last,
        "street": street,
        "city": city,
        "zip": zip_code,
        "lot": lot,
        "block": block,
        "status": norm_status(row.get("status", "")),
        "attorney": row.get("attorney", ""),
        "parcel_raw": row.get("parcel", ""),
        "court_case": row.get("court_case", ""),
        "judgment": row.get("judgment", ""),
        "status_history": row.get("status_history", ""),
    }
