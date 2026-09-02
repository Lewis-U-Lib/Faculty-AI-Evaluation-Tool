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
    - invalid specimen classes, provenance values, or source references
    - duplicate specimen ids or specimens missing required fields
    - specimen classes absent from either HTML renderer map
    - missing templates that prevent renderer validation
    - rules with no activities
    - malformed URLs in sources
  WARNINGS problems a human should look at
    - "can support" + bare infinitive (residue of the May 2026 rewrite)
    - other known copy errors
    - unqualified efficacy claims (ensures / dramatically / perfect / essential)
    - runtime metadata coverage below 100% (tier, mode, bloom)
    - sources defined but never referenced by activity mappings or specimens
"""
import argparse
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BUILD_CONFIG = ROOT / "build.json"

# The renderers group specimens by this map and skip classes absent from it.
# Checking data alone cannot catch a valid specimen that silently never renders.
SPECIMEN_CLASS_MAP = re.compile(r"var SPECIMEN_CLASSES\s*=\s*\{(.*?)\};", re.S)
SPECIMEN_CLASS_KEY = re.compile(r"(?:^|,)\s*([A-Za-z_]\w*)\s*:", re.M)

REQUIRED_ACTIVITY_FIELDS = ["title", "desc", "time", "bloom", "tags", "instructions", "mode", "tier"]
# `arch` is retained where it already exists for editorial history, but it is
# not consumed by either runtime and is not part of the required activity
# schema. Coverage checks therefore apply only to metadata the site uses.
COVERAGE_FIELDS = ["tier", "mode", "bloom"]
SPECIMEN_REQUIRED_FIELDS = [
    "id", "defect_class", "domain", "difficulty", "scenario", "specimen",
    "defects", "verification_path", "teaching_note", "serves", "provenance",
]
SPECIMEN_CLASSES = {
    "fabricated_citation", "bias_stereotype", "translation_loss",
    "quantitative_error", "confident_wrong", "entity_error", "relation_error",
    "incompleteness", "outdatedness", "overclaim", "unverifiability",
    "prompt_assumption_expansion", "reasoning_error", "logic_error",
}
SPECIMEN_PROVENANCE = {"constructed", "captured", "captured_from_literature"}

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
    specimens = load("specimens")
    activities = [a for r in rules for a in r.get("activities", []) if isinstance(a, dict)]
    stats.update(rules=len(rules), activities=len(activities), sources=len(sources),
                 specimens=len(specimens))

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

    for specimen_id, n in collections.Counter(s.get("id") for s in specimens).items():
        if specimen_id and n > 1:
            errors.append(f"duplicate specimen id {specimen_id!r} appears {n} times")

    for specimen in specimens:
        specimen_id = specimen.get("id", "?")
        missing = [field for field in SPECIMEN_REQUIRED_FIELDS
                   if specimen.get(field) in (None, "", [])]
        if missing:
            errors.append(f"specimen {specimen_id!r} missing {missing}")
        if specimen.get("defect_class") not in SPECIMEN_CLASSES:
            errors.append(f"specimen {specimen_id!r} has unknown defect class "
                          f"{specimen.get('defect_class')!r}")
        provenance = specimen.get("provenance")
        if provenance not in SPECIMEN_PROVENANCE:
            errors.append(f"specimen {specimen_id!r} has unknown provenance {provenance!r}")
        if provenance == "captured_from_literature" and not specimen.get("instance_source"):
            errors.append(f"specimen {specimen_id!r} is literature-sourced but has no instance_source")

        specimen_source_ids = set(specimen.get("defect_class_source") or [])
        if specimen.get("instance_source"):
            specimen_source_ids.add(specimen["instance_source"])
        referenced |= specimen_source_ids
        for sid in sorted(specimen_source_ids - set(sources)):
            errors.append(f"specimen {specimen_id!r} references undefined source id {sid!r}")

    # --- specimen renderer maps -----------------------------------------
    # build.json is authoritative for the templates that become published
    # pages. Each one must explicitly list every class present in the data.
    try:
        build_config = json.loads(BUILD_CONFIG.read_text(encoding="utf-8"))
        template_paths = [ROOT / target["template"]
                          for target in build_config.get("targets", [])
                          if target.get("template")]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
        template_paths = []
        errors.append(f"cannot load template paths from build.json: {exc}")

    if not template_paths:
        errors.append("build.json defines no templates; cannot verify specimen renderers")

    data_classes = {specimen.get("defect_class") for specimen in specimens
                    if specimen.get("defect_class")}
    renderer_classes = {}
    for template_path in template_paths:
        if not template_path.is_file():
            errors.append(f"missing template {template_path.relative_to(ROOT)}; "
                          "cannot verify its specimen renderer")
            continue
        match = SPECIMEN_CLASS_MAP.search(template_path.read_text(encoding="utf-8"))
        if not match:
            errors.append(f"{template_path.name}: no SPECIMEN_CLASSES map found")
            continue
        declared = set(SPECIMEN_CLASS_KEY.findall(match.group(1)))
        renderer_classes[template_path.name] = declared
        for specimen_class in sorted(data_classes - declared):
            count = sum(1 for specimen in specimens
                        if specimen.get("defect_class") == specimen_class)
            errors.append(f"{template_path.name}: defect class {specimen_class!r} "
                          f"is used by {count} specimen(s) but is absent from "
                          "SPECIMEN_CLASSES, so those cards will not render")
        for specimen_class in sorted(declared - data_classes):
            warnings.append(f"{template_path.name}: SPECIMEN_CLASSES lists "
                            f"{specimen_class!r}, but no specimen uses it")

    if len(renderer_classes) > 1:
        names = sorted(renderer_classes)
        baseline_name = names[0]
        baseline = renderer_classes[baseline_name]
        for name in names[1:]:
            if renderer_classes[name] != baseline:
                errors.append(f"specimen renderer maps disagree: {baseline_name} and {name}")

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
        warnings.append(f"{len(unused)} sources defined but not referenced by activity mappings or specimens")

    # --- report -----------------------------------------------------------
    if args.as_json:
        print(json.dumps({"stats": stats, "errors": errors, "warnings": warnings}, indent=1))
    else:
        print(f"rules={stats['rules']}  activities={stats['activities']}  "
              f"sources={stats['sources']}  specimens={stats['specimens']}")
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
