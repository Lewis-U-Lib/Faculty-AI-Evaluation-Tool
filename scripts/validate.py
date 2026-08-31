#!/usr/bin/env python3
"""
validate.py — schema, integrity and editorial checks over canonical data/

Run before every build. Exits non-zero on ERROR so it can gate publication.
Warnings do not block by default; --strict promotes them to errors.

    python3 scripts/validate.py
    python3 scripts/validate.py --strict
    python3 scripts/validate.py --json          # machine-readable report

Checks
  ERRORS   structural problems that would ship a broken tool
    - activities missing a required field
    - duplicate activity titles
    - source ids referenced by the mapping layers but absent from sources.json
    - rules with no activities
    - malformed URLs in sources
  WARNINGS problems a human should look at
    - "can support" + bare infinitive (residue of the May 2026 rewrite)
    - other known copy errors
    - unqualified efficacy claims (ensures / dramatically / perfect / essential)
    - runtime metadata coverage below 100% (tier, mode, bloom)
    - sources defined but never referenced anywhere
"""
import argparse
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

REQUIRED_ACTIVITY_FIELDS = ["title", "desc", "time", "bloom", "tags", "instructions", "mode", "tier"]
# `arch` is retained where it already exists for editorial history, but it is
# not consumed by either runtime and is not part of the required activity
# schema. Coverage checks therefore apply only to metadata the site uses.
COVERAGE_FIELDS = ["tier", "mode", "bloom"]

MALFORMED = re.compile(
    r"can support (?:scope|draft|build|create|design|generate|identify|compare|analyze"
    r"|write|map|test|explore|evaluate|summarize|translate|check|run|produce)\b")
COPY_ERRORS = [(re.compile(r"What would you can\b"), "'What would you can' — should be 'What could you'")]
EFFICACY = re.compile(r"\b(ensures|dramatically|perfect|essential)\b", re.I)


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()

    errors, warnings, stats = [], [], {}

    rules = load("rules")
    sources = load("sources")
    activities = [a for r in rules for a in r.get("activities", []) if isinstance(a, dict)]
    stats.update(rules=len(rules), activities=len(activities), sources=len(sources))

    # --- structural -------------------------------------------------------
    for r in rules:
        if not r.get("activities"):
            errors.append(f"rule {r.get('id','?')!r} has no activities")

    for a in activities:
        missing = [f for f in REQUIRED_ACTIVITY_FIELDS if not a.get(f)]
        if missing:
            errors.append(f"activity {a.get('title','?')[:48]!r} missing {missing}")

    for title, n in collections.Counter(a.get("title") for a in activities).items():
        if n > 1:
            errors.append(f"duplicate activity title {title!r} appears {n} times")

    referenced = set()
    for store in ("kw_sources", "rule_fallback", "bloom_src"):
        try:
            blob = json.dumps(load(store))
        except FileNotFoundError:
            continue
        ids = set(re.findall(r'"([a-z][\w]*\d{4}[a-z]?)"', blob))
        referenced |= ids
        for sid in sorted(ids - set(sources)):
            errors.append(f"{store}: references undefined source id {sid!r}")

    for sid, rec in sources.items():
        url = rec.get("url", "")
        if url and not re.match(r"^https?://", url) and not rec.get("retired"):
            errors.append(f"source {sid!r} has a malformed url: {url[:60]!r}")

    # --- editorial --------------------------------------------------------
    for a in activities:
        text = " ".join(str(a.get(f, "")) for f in ("title", "desc", "instructions"))
        if MALFORMED.search(text):
            warnings.append(f"malformed 'can support' + infinitive: {a['title']}")
        for pattern, label in COPY_ERRORS:
            if pattern.search(text):
                warnings.append(f"copy error ({label}): {a['title']}")

    efficacy = [a["title"] for a in activities
                if EFFICACY.search(" ".join(str(a.get(f, "")) for f in ("desc", "instructions")))]
    if efficacy:
        warnings.append(f"unqualified efficacy language in {len(efficacy)} activities "
                        f"(ensures/dramatically/perfect/essential)")
    stats["efficacy_flagged"] = len(efficacy)

    for field in COVERAGE_FIELDS:
        have = sum(1 for a in activities if a.get(field) not in (None, "", []))
        pct = 100 * have // max(1, len(activities))
        stats[f"coverage_{field}"] = f"{have}/{len(activities)} ({pct}%)"
        if pct < 100:
            warnings.append(f"{field} coverage {have}/{len(activities)} ({pct}%)")

    unused = sorted(set(sources) - referenced)
    stats["sources_unreferenced"] = len(unused)
    if unused:
        warnings.append(f"{len(unused)} sources defined but not referenced by any mapping layer")

    # --- report -----------------------------------------------------------
    if args.as_json:
        print(json.dumps({"stats": stats, "errors": errors, "warnings": warnings}, indent=1))
    else:
        print(f"rules={stats['rules']}  activities={stats['activities']}  sources={stats['sources']}")
        for k, v in stats.items():
            if k.startswith("coverage_"):
                print(f"  {k[9:]:<10} {v}")
        for w in warnings:
            print(f"  WARN   {w}")
        for e in errors:
            print(f"  ERROR  {e}")
        print(f"\n{len(errors)} errors, {len(warnings)} warnings")

    if errors or (args.strict and warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
