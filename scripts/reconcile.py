#!/usr/bin/env python3
"""
reconcile.py — resolve divergences found by extract.py into canonical data.

extract.py keeps the first value it sees and records disagreements in
divergences.json. This script merges the two published files field by field so
the canonical record is a superset rather than an arbitrary winner.

Merge policy:
  * A field present in one file and absent in the other is ADOPTED.
    (This is how BIB's "access" flag reaches canonical sources.json.)
  * A field present in both with different values is a CONFLICT. It is left at
    the extract.py value and reported for a human decision.

Usage:
    python3 scripts/reconcile.py --index <file> --reference <file>
    python3 scripts/reconcile.py --index <file> --reference <file> --apply
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from extract import find_literal, js_to_json, to_object  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "build.json").read_text(encoding="utf-8"))


def collect(path, target):
    doc = pathlib.Path(path).read_text(encoding="utf-8")
    out = {}
    for store, datafile in target["stores"].items():
        loc = find_literal(doc, store)
        if loc:
            out[datafile] = to_object(js_to_json(loc[2], store), datafile)
    return out


def merge(a, b, label_a, label_b):
    """Merge two id-keyed dicts. Returns (merged, adopted, conflicts)."""
    merged = json.loads(json.dumps(a))
    adopted, conflicts = [], []
    for key in set(a) | set(b):
        va, vb = a.get(key), b.get(key)
        if va is None:
            merged[key] = vb
            adopted.append(f"{key} (only in {label_b})")
            continue
        if vb is None or va == vb:
            continue
        if not (isinstance(va, dict) and isinstance(vb, dict)):
            conflicts.append({"key": key, label_a: va, label_b: vb})
            continue
        for field in set(va) | set(vb):
            fa, fb = va.get(field), vb.get(field)
            if fa == fb:
                continue
            if fa is None:
                merged[key][field] = fb
                adopted.append(f"{key}.{field} (only in {label_b})")
            elif fb is None:
                adopted.append(f"{key}.{field} (only in {label_a})")
            else:
                conflicts.append({"key": f"{key}.{field}", label_a: fa, label_b: fb})
    return merged, adopted, conflicts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--apply", action="store_true", help="write merged result to data/")
    args = ap.parse_args()

    by_target = {t["name"]: t for t in CFG["targets"]}
    idx = collect(args.index, by_target["index"])
    ref = collect(args.reference, by_target["reference"])

    all_adopted, all_conflicts = [], []
    for datafile in sorted(set(idx) & set(ref)):
        if idx[datafile] == ref[datafile]:
            continue
        if not isinstance(idx[datafile], dict):
            continue
        merged, adopted, conflicts = merge(idx[datafile], ref[datafile], "index", "reference")
        print(f"\n{datafile}.json")
        print(f"  fields adopted from the other file: {len(adopted)}")
        for a in adopted[:6]:
            print(f"    + {a}")
        if len(adopted) > 6:
            print(f"    ... and {len(adopted)-6} more")
        print(f"  conflicts needing a decision: {len(conflicts)}")
        for c in conflicts:
            print(f"    ! {c['key']}")
            print(f"        index    : {str(c['index'])[:96]}")
            print(f"        reference: {str(c['reference'])[:96]}")
        all_adopted += adopted
        all_conflicts += conflicts
        if args.apply:
            path = ROOT / "data" / f"{datafile}.json"
            path.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  -> wrote data/{datafile}.json")

    (ROOT / "divergences.json").write_text(json.dumps({
        "adopted": all_adopted,
        "conflicts": all_conflicts,
        "note": "Conflicts are left at the index value. Edit data/ to resolve.",
    }, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"\n{len(all_adopted)} fields adopted, {len(all_conflicts)} conflicts")
    if not args.apply:
        print("dry run — re-run with --apply to write data/")
    elif all_conflicts:
        print("Conflicts remain at the index value. Edit data/ to change that.")


if __name__ == "__main__":
    main()
