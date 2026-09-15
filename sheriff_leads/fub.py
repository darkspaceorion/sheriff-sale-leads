"""Follow Up Boss client. Verified against docs.followupboss.com on 2026-09-15.

Auth: HTTP Basic, API key as username, blank password.
Create lead: POST /v1/events (runs their automations, logs the event).
Find by custom field: GET /v1/people?customCaseNumber=XYZ
Rate limit: 10-second sliding window, 125 calls without X-System-Key, 200 with.
"""
import os
import time

import requests

BASE = "https://api.followupboss.com/v1"


class FUBError(Exception):
    pass


class FUB:
    def __init__(self, api_key: str | None = None, system: str = "Procilium-SheriffSale",
                 system_key: str | None = None):
        self.auth = (api_key or os.environ["FUB_API_KEY"], "")
        self.headers = {"X-System": system, "Content-Type": "application/json"}
        sk = system_key or os.environ.get("FUB_SYSTEM_KEY")
        if sk:
            self.headers["X-System-Key"] = sk

    def _call(self, method: str, path: str, retries: int = 3, **kw) -> dict:
        for attempt in range(retries):
            r = requests.request(method, f"{BASE}{path}", auth=self.auth,
                                 headers=self.headers, timeout=30, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt * 2)  # 2s, 4s, 8s
                continue
            if r.status_code >= 400:
                raise FUBError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
            time.sleep(0.2)  # stay well under the 10-second window limit
            return r.json() if r.text else {}
        raise FUBError(f"{method} {path} failed after {retries} retries (last {r.status_code})")

    def find_by_case(self, field: str, case_number: str) -> dict | None:
        data = self._call("GET", "/people", params={field: case_number, "limit": 1})
        people = data.get("people", [])
        return people[0] if people else None

    def create_lead(self, lead: dict, cfg: dict) -> dict:
        cf = cfg["custom_fields"]
        person = {
            "firstName": lead["first_name"],
            "lastName": lead["last_name"],
            "source": f"{cfg['source_prefix']} - {lead['county']}",
            "tags": cfg["tags"] + [lead["county"].replace(" ", "-").lower()],
            "addresses": [{
                "type": "home",
                "street": lead["street"],
                "city": lead["city"],
                "state": lead["state"],
                "code": lead["zip"],
            }],
            cf["case_number"]: lead["case_number"],
            cf["status"]: lead["status"],
            cf["plaintiff"]: lead["plaintiff"],
            cf["attorney"]: lead["attorney"],
            cf["lot_block"]: (f"Lot {lead['lot']} Block {lead['block']}" if lead["lot"] else lead.get("parcel_raw", "")),
            cf["sale_date"]: lead["sale_date"],
            cf["defendant_raw"]: lead["defendant_raw"],
            cf["court_case"]: lead.get("court_case", ""),
            cf["judgment"]: lead.get("judgment", ""),
        }
        payload = {
            "source": person["source"],
            "system": self.headers["X-System"],
            "type": "General Inquiry",
            "message": f"Sheriff sale listing. Case {lead['case_number']}, status {lead['status']}.",
            "person": person,
        }
        return self._call("POST", "/events", json=payload)

    def update_status(self, person_id: int, status: str, cfg: dict, note: str = "") -> dict:
        out = self._call("PUT", f"/people/{person_id}", json={cfg["custom_fields"]["status"]: status})
        if note:
            self._call("POST", "/notes", json={"personId": person_id, "subject": "Sheriff sale update", "body": note})
        return out


class FakeFUB(FUB):
    """Demo stand-in. Same methods, no network. Prints what would be sent.
    Used by `main.py --fake-fub` so the dedupe path can be shown on camera without a key."""

    def __init__(self):
        self.headers = {"X-System": "Procilium-SheriffSale (fake)"}
        self._next = 1000
        self._by_case: dict[str, dict] = {}

    def find_by_case(self, field, case_number):
        return self._by_case.get(case_number)

    def create_lead(self, lead, cfg):
        self._next += 1
        self._by_case[lead["case_number"]] = {"id": self._next}
        print(f"    FUB(fake) POST /v1/events  {lead['first_name']} {lead['last_name']}  "
              f"{lead['street']}, {lead['city']}  case {lead['case_number']}  -> person #{self._next}")
        return {"id": self._next}

    def update_status(self, person_id, status, cfg, note=""):
        print(f"    FUB(fake) PUT /v1/people/{person_id}  {cfg['custom_fields']['status']}={status}")
        if note:
            print(f"    FUB(fake) POST /v1/notes  #{person_id}: {note}")
        return {}
