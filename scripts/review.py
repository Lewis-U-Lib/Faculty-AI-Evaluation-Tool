#!/usr/bin/env python3
"""
review.py — move content review out of HTML and into a spreadsheet.

export  data/  ->  review/activities.csv, review/sources.csv
import  reviewed CSV  ->  data/   (validated, additive, never destructive)

This is what lets a subject librarian review 1,131 activities in Excel without
touching code. Reviewer columns (reviewed_by, reviewed_on, review_note) are
carried through so partial progress is visible and resumable.

    python3 scripts/review.py export
    python3 scripts/review.py import --file review/activities.csv
    python3 scripts/review.py import --file review/activities.csv --apply

Import is keyed on rule_id + title. Rows whose key is not found are reported
and skipped rather than guessed at. Structural fields (rule_id, title) cannot
be changed through import — rename in data/ instead, deliberately.
"""
import argparse
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA, REVIEW = ROOT / "data", ROOT / "review"

ACTIVITY_COLUMNS = [
    "rule_id", "title", "bloom", "mode", "tier", "arch", "time",
    "tags", "desc", "instructions",
    "reviewed_by", "reviewed_on", "review_note",
]
EDITABLE = ["bloom", "mode", "tier", "arch", "time", "tags", "desc", "instructions",
            "reviewed_by", "reviewed_on", "review_note"]

SOURCE_COLUMNS = ["id", "short", "cite", "url", "access", "retired",
                  "reviewed_by", "reviewed_on", "review_note"]
SOURCE_EDITABLE = ["short", "cite", "url", "access", "retired",
                   "reviewed_by", "reviewed_on", "review_note"]


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def save(name, value):
    (DATA / f"{name}.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")


def flatten(value):
    return "; ".join(value) if isinstance(value, list) else ("" if value is None else str(value))


def do_export():
    REVIEW.mkdir(exist_ok=True)
    rules = load("rules")
    rows = 0
    with (REVIEW / "activities.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=ACTIVITY_COLUMNS)
        w.writeheader()
        for rule in rules:
            for a in rule.get("activities", []):
                if not isinstance(a, dict):
                    continue
                w.writerow({c: flatten(a.get(c)) if c not in ("rule_id",) else rule.get("id", "")
                            for c in ACTIVITY_COLUMNS})
                rows += 1
    print(f"  review/activities.csv   {rows} rows")

    sources = load("sources")
    with (REVIEW / "sources.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=SOURCE_COLUMNS)
        w.writeheader()
        for sid, rec in sorted(sources.items()):
            row = {c: flatten(rec.get(c)) for c in SOURCE_COLUMNS}
            row["id"] = sid
            w.writerow(row)
    print(f"  review/sources.csv      {len(sources)} rows")
    print("\nEdit in Excel or Sheets. Do not change rule_id/title or id — those are keys.")
    print("Re-import with: python3 scripts/review.py import --file review/<name>.csv")


def unflatten(column, text):
    text = (text or "").strip()
    if column == "tags":
        return [t.strip() for t in text.split(";") if t.strip()] if text else []
    if column == "tier":
        return int(text) if text.isdigit() else (text or None)
    if column == "retired":
        return True if text.lower() in ("true", "yes", "1") else None
    return text or None


def do_import(path, apply_changes):
    path = pathlib.Path(path)
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    if not rows:
        raise SystemExit("empty CSV")

    is_sources = "id" in rows[0] and "rule_id" not in rows[0]
    changes, unmatched = [], []

    if is_sources:
        sources = load("sources")
        for r in rows:
            sid = (r.get("id") or "").strip()
            if sid not in sources:
                unmatched.append(sid)
                continue
            for col in SOURCE_EDITABLE:
                if col not in r:
                    continue
                new = unflatten(col, r[col])
                old = sources[sid].get(col)
                if new != old and not (new is None and old is None):
                    changes.append((sid, col, old, new))
                    if apply_changes:
                        if new is None:
                            sources[sid].pop(col, None)
                        else:
                            sources[sid][col] = new
        if apply_changes:
            save("sources", sources)
    else:
        rules = load("rules")
        index = {}
        for rule in rules:
            for a in rule.get("activities", []):
                if isinstance(a, dict):
                    index[(rule.get("id", ""), a.get("title", ""))] = a
        for r in rows:
            key = ((r.get("rule_id") or "").strip(), (r.get("title") or "").strip())
            target = index.get(key)
            if target is None:
                unmatched.append(f"{key[0]} / {key[1][:40]}")
                continue
            for col in EDITABLE:
                if col not in r:
                    continue
                new = unflatten(col, r[col])
                old = target.get(col)
                if new != old and not (new is None and old is None):
                    changes.append((key[1][:40], col, old, new))
                    if apply_changes:
                        if new is None:
                            target.pop(col, None)
                        else:
                            target[col] = new
        if apply_changes:
            save("rules", rules)

    print(f"{len(rows)} rows read, {len(changes)} field change(s), {len(unmatched)} unmatched")
    for key, col, old, new in changes[:15]:
        print(f"  {key} · {col}")
        print(f"      - {str(old)[:88]}")
        print(f"      + {str(new)[:88]}")
    if len(changes) > 15:
        print(f"  ... and {len(changes)-15} more")
    for u in unmatched[:10]:
        print(f"  UNMATCHED (skipped): {u}")
    if not apply_changes:
        print("\ndry run — re-run with --apply to write data/, then run validate.py and build.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["export", "import"])
    ap.add_argument("--file")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.mode == "export":
        do_export()
    else:
        if not args.file:
            raise SystemExit("import needs --file")
        do_import(args.file, args.apply)


if __name__ == "__main__":
    main()
