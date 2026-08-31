#!/usr/bin/env python3
"""
extract.py — one-time migration: published HTML  ->  canonical data/ + templates/

Reads the currently published index and Reference files, lifts every data store
out of them, converts each to canonical JSON, and rewrites the HTML as a template
with inert markers in place of the data.

Run this ONCE to adopt the pipeline. After that, data/ is the source of truth and
this script is only needed if you ever need to re-migrate from a hand-edited file.

Usage:
    python3 scripts/extract.py --index path/to/6.9.index.html \
                               --reference path/to/Reference_29.html

Requires: python3 (stdlib), node (to evaluate JavaScript object literals exactly).
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "build.json").read_text(encoding="utf-8"))


def find_literal(doc, name):
    """Locate `var NAME = <literal>` and return (start, end, text).

    Uses a string-aware bracket matcher: quotes and escapes are tracked so that
    braces or brackets inside string values do not terminate the scan early.
    """
    for opener, closer in (("{", "}"), ("[", "]")):
        pattern = re.compile(
            r"(?:var|const|let)\s+" + re.escape(name) + r"\s*=\s*" + re.escape(opener)
        )
        m = pattern.search(doc)
        if not m:
            continue
        start = m.end() - 1
        i, depth, in_str, esc, quote = start, 0, False, False, ""
        while i < len(doc):
            c = doc[i]
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif in_str:
                if c == quote:
                    in_str = False
            elif c in "\"'":
                in_str, quote = True, c
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return m.start(), i + 1, doc[start:i + 1]
            i += 1
    return None


def js_to_json(literal, label):
    """Convert a JavaScript object/array literal to JSON via node.

    Node is used rather than a regex so that unquoted keys, single-quoted
    strings, trailing commas and JS-only escapes (\\') all convert exactly.
    """
    script = "const X = " + literal + ";\nprocess.stdout.write(JSON.stringify(X));"
    tmp = ROOT / ".extract_tmp.js"
    tmp.write_text(script, encoding="utf-8")
    try:
        p = subprocess.run(["node", str(tmp)], capture_output=True, text=True)
    finally:
        tmp.unlink(missing_ok=True)
    if p.returncode != 0:
        raise SystemExit(f"  ERROR converting {label}: {p.stderr.strip().splitlines()[-1][:160]}")
    return json.loads(p.stdout)


ID_KEYED = set(CFG.get("id_keyed", []))


def to_object(value, datafile=None):
    """Normalise an id-bearing array into an object keyed by id.

    Only canonical files named in build.json "id_keyed" are converted. This is
    declared rather than inferred on purpose: RULES entries also carry unique
    ids, but RULES is an ordered array whose order drives rule priority, and
    re-keying it would silently change matching behaviour.
    """
    if datafile not in ID_KEYED:
        return value
    if not isinstance(value, list) or not value:
        return value
    if not all(isinstance(x, dict) and "id" in x for x in value):
        return value
    return {x["id"]: {k: v for k, v in x.items() if k != "id"} for x in value}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--reference", required=True)
    args = ap.parse_args()

    sources = {"index": pathlib.Path(args.index), "reference": pathlib.Path(args.reference)}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "templates").mkdir(exist_ok=True)

    canonical, provenance, divergences = {}, {}, []

    for target in CFG["targets"]:
        name = target["name"]
        doc = sources[name].read_text(encoding="utf-8")
        spans = []
        print(f"\n{name}  ({sources[name].name}, {len(doc)/1024:.0f} KB)")

        for store, datafile in target["stores"].items():
            loc = find_literal(doc, store)
            if not loc:
                print(f"  {store:<20} NOT FOUND — skipped")
                continue
            start, end, literal = loc
            value = to_object(js_to_json(literal, f"{name}.{store}"), datafile)
            spans.append((start, end, store))

            if datafile in canonical:
                if canonical[datafile] != value:
                    keys = set(canonical[datafile]) | set(value)
                    differing = [
                        k for k in keys
                        if canonical[datafile].get(k) != value.get(k)
                    ]
                    divergences.append({
                        "datafile": datafile,
                        "stores": [provenance[datafile], f"{name}.{store}"],
                        "differing_keys": differing[:50],
                        "count": len(differing),
                        "resolution": f"kept value from {provenance[datafile]}",
                    })
                    print(f"  {store:<20} DIVERGENT from {provenance[datafile]} "
                          f"({len(differing)} key(s)) — see divergences.json")
                else:
                    print(f"  {store:<20} matches {provenance[datafile]}")
            else:
                canonical[datafile] = value
                provenance[datafile] = f"{name}.{store}"
                print(f"  {store:<20} -> data/{datafile}.json  ({len(literal):,} bytes)")

        for start, end, store in sorted(spans, reverse=True):
            doc = doc[:start] + f"var {store} = /*@@{store}@@*/null;" + doc[end:]

        out = ROOT / target["template"]
        out.write_text(doc, encoding="utf-8")
        print(f"  -> {target['template']}  ({len(doc)/1024:.0f} KB shell)")

    for datafile, value in canonical.items():
        path = ROOT / "data" / f"{datafile}.json"
        path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")

    (ROOT / "data" / "_provenance.json").write_text(
        json.dumps(provenance, indent=1), encoding="utf-8")
    (ROOT / "divergences.json").write_text(
        json.dumps(divergences, indent=1), encoding="utf-8")

    total = sum((ROOT / "data" / f"{d}.json").stat().st_size for d in canonical)
    print(f"\ncanonical data: {len(canonical)} files, {total/1024:.0f} KB")
    if divergences:
        print(f"UNRESOLVED DIVERGENCES: {len(divergences)} — review divergences.json "
              f"and correct data/ before publishing.")
    else:
        print("no divergences: both files agreed on every shared store.")


if __name__ == "__main__":
    main()
