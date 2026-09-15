"""Sheriff sale leads -> Follow Up Boss.

Usage:
  python main.py                      full run, all counties in config.yaml
  python main.py --county "Example County"
  python main.py --dry-run            parse + dedupe, print what WOULD go to FUB, no writes
  python main.py --dry-run --county "Monmouth County" --limit 8
                                      live CivilView pull, first 8 listings only
  python main.py --pdf path/to/file.pdf --county "Example County"
                                      proof-of-concept mode: parse a local PDF to CSV only
  python main.py --pdf ../sample/sample_sale_list.pdf --county "Example County" --fake-fub
                                      dedupe demo: run twice, second run shows 0 new (no key needed)
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

import fallback
import notify
from normalize import normalize
from sources import civilview, pdf_source

ROOT = Path(__file__).parent
DATA = ROOT / "data"
SEEN = DATA / "seen.json"          # {case_number: {"status": ..., "fub_id": ..., "county": ...}}
HASHES = DATA / "hashes.json"      # {county: sha256 of last file}


def load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def save_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True))


def run(args):
    load_dotenv(ROOT / ".env")
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    counties = [c for c in cfg["counties"] if not args.county or c["name"] == args.county]
    if not counties:
        sys.exit(f"No county named {args.county!r} in config.yaml")

    seen, hashes = load_json(SEEN, {}), load_json(HASHES, {})
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new, updated, failed, errors, mirror = [], [], [], [], []

    fub = None
    if args.fake_fub:
        from fub import FakeFUB
        fub = FakeFUB()
        fub._next = max([v.get("fub_id") or 1000 for v in seen.values()] + [1000])
    elif not (args.dry_run or args.pdf):
        from fub import FUB
        fub = FUB()

    for county in counties:
        # ---- 1. fetch rows from the right source -------------------------------
        try:
            if args.pdf:
                rows = pdf_source.parse_tables(Path(args.pdf), county["columns"],
                                               county.get("table_strategy", "lines"))
                digest = "local"
            elif county["type"] == "pdf":
                rows, digest = pdf_source.fetch(county, DATA / "raw")
            elif county["type"] == "civilview":
                rows, digest = civilview.fetch(county, limit=args.limit)
            else:
                raise ValueError(f"unknown source type {county['type']}")
        except Exception as e:
            errors.append(f"{county['name']}: {e}")
            print(f"[{county['name']}] ERROR {e}")
            continue

        if digest != "local" and hashes.get(county["name"]) == digest:
            print(f"[{county['name']}] unchanged since last run, skipping")
            continue
        hashes[county["name"]] = digest
        print(f"[{county['name']}] {len(rows)} rows parsed")

        # ---- 2. normalise, dedupe, push -----------------------------------------
        for raw in rows:
            lead = normalize(raw, county)
            lead["run_at"] = run_at
            key = lead["case_number"]
            if not key:
                continue
            prior = seen.get(key)

            if (args.pdf or args.dry_run) and not args.fake_fub:
                lead["fub_result"] = "dry-run" if prior is None else f"dup (status {prior['status']})"
                (new if prior is None else updated).append(lead)
                mirror.append(lead)
                continue

            try:
                if prior is None:
                    # belt and braces: ask FUB too, in case seen.json is fresh
                    existing = fub.find_by_case(cfg["fub"]["custom_fields"]["case_number"], key)
                    if existing:
                        seen[key] = {"status": lead["status"], "fub_id": existing["id"], "county": lead["county"]}
                        lead["fub_result"] = f"already in FUB #{existing['id']}"
                    else:
                        res = fub.create_lead(lead, cfg["fub"])
                        pid = res.get("id") or res.get("personId")
                        seen[key] = {"status": lead["status"], "fub_id": pid, "county": lead["county"]}
                        lead["fub_result"] = f"created #{pid}"
                        new.append(lead)
                elif prior["status"] != lead["status"]:
                    fub.update_status(prior["fub_id"], lead["status"], cfg["fub"],
                                      note=f"Status changed {prior['status']} -> {lead['status']} (run {run_at})")
                    seen[key]["status"] = lead["status"]
                    lead["fub_result"] = f"updated #{prior['fub_id']}"
                    updated.append(lead)
                else:
                    lead["fub_result"] = "unchanged"
            except Exception as e:
                lead["fub_result"] = f"FAILED {e}"
                failed.append(lead)
                errors.append(f"{key}: {e}")
            mirror.append(lead)

    # ---- 3. mirror, fallback, alert ----------------------------------------------
    out_csv = DATA / ("poc_output.csv" if args.pdf else "all_rows.csv")
    fallback.append_csv(out_csv, mirror)
    if failed:
        fallback.append_csv(DATA / "fallback.csv", failed)
    if args.fake_fub or not (args.pdf or args.dry_run):
        if not args.fake_fub:
            fallback.append_sheet(mirror)
        save_json(SEEN, seen)
        save_json(HASHES, hashes)

    body = notify.summary(new, updated, failed, errors)
    print("\n" + body)
    if not (args.pdf or args.dry_run) and (new or updated or failed or errors):
        notify.send(f"{cfg['alerts']['subject_prefix']} {len(new)} new, {len(updated)} updated",
                    body, cfg["alerts"]["to"])
    print(f"\nWrote {len(mirror)} rows to {out_csv}")
    return 1 if errors and not (new or updated) else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--county")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pdf", help="parse a local PDF only (proof-of-concept mode)")
    ap.add_argument("--fake-fub", action="store_true",
                    help="demo: run the real dedupe/push path against an in-memory FUB stub, saves seen.json")
    ap.add_argument("--limit", type=int, help="CivilView: only fetch the first N listings (demo / testing)")
    sys.exit(run(ap.parse_args()))
