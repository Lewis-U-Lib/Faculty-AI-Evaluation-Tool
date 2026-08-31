#!/usr/bin/env python3
"""
roundtrip_test.py — prove the pipeline preserves meaning.

Compares every data store in dist/ against the same store in the original
published files, after parsing both through node. Byte-identity is NOT the
test: serialisation differs by design (canonical JSON quotes keys, drops the
JS-only \\' escape). Semantic identity is the test.

Also checks cross-file parity: every store shared by the two outputs must be
identical, which is the guarantee the whole split exists to provide.

    python3 scripts/roundtrip_test.py --index <original> --reference <original>

Exits non-zero on any mismatch. Safe to wire into a pre-publish hook.
"""
import argparse
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from extract import find_literal  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "build.json").read_text(encoding="utf-8"))


def parse_store(doc, name):
    loc = find_literal(doc, name)
    if not loc:
        return None
    script = "const X = " + loc[2] + ";\nprocess.stdout.write(JSON.stringify(X));"
    tmp = ROOT / ".rt_tmp.js"
    tmp.write_text(script, encoding="utf-8")
    try:
        p = subprocess.run(["node", str(tmp)], capture_output=True, text=True)
    finally:
        tmp.unlink(missing_ok=True)
    if p.returncode != 0:
        return "PARSE_FAIL"
    return json.loads(p.stdout)


def normalise(value):
    """Collapse shape differences so index and Reference compare on content."""
    if isinstance(value, list) and value and all(
            isinstance(x, dict) and "id" in x for x in value):
        ids = [x["id"] for x in value]
        if len(set(ids)) == len(ids):
            return {x["id"]: {k: v for k, v in x.items() if k != "id"} for x in value}
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--reference", required=True)
    args = ap.parse_args()

    originals = {"index": args.index, "reference": args.reference}
    failures = []
    parsed = {}

    # Differences the reconciliation step deliberately introduced are expected,
    # not regressions: adopted fields (e.g. BIB's "access" reaching SOURCES) and
    # resolved conflicts. Anything else is a genuine failure.
    reconciled = set()
    div = ROOT / "divergences.json"
    if div.exists():
        record = json.loads(div.read_text(encoding="utf-8"))
        if isinstance(record, dict):
            for entry in record.get("adopted", []):
                reconciled.add(entry.split(" ")[0])
            for entry in record.get("conflicts", []):
                reconciled.add(entry["key"])

    def explain(a, b):
        """Return the set of key paths that differ between two stores."""
        if not (isinstance(a, dict) and isinstance(b, dict)):
            return {"<whole store>"}
        changed = set()
        for key in set(a) | set(b):
            va, vb = a.get(key), b.get(key)
            if va == vb:
                continue
            if isinstance(va, dict) and isinstance(vb, dict):
                for f in set(va) | set(vb):
                    if va.get(f) != vb.get(f):
                        changed.add(f"{key}.{f}")
            else:
                changed.add(key)
        return changed

    for target in CFG["targets"]:
        name = target["name"]
        orig = pathlib.Path(originals[name]).read_text(encoding="utf-8")
        built = (ROOT / "dist" / target["output"]).read_text(encoding="utf-8")
        print(f"\n{name}: dist/{target['output']} vs {pathlib.Path(originals[name]).name}")
        parsed[name] = {}
        for store in target["stores"]:
            a, b = parse_store(orig, store), parse_store(built, store)
            parsed[name][store] = b
            if a is None and b is None:
                continue
            if a == b:
                print(f"  {store:<20} identical")
                continue
            changed = explain(normalise(a), normalise(b))
            unexplained = changed - reconciled
            if unexplained:
                failures.append(f"{name}.{store}")
                sample = sorted(unexplained)[:3]
                print(f"  {store:<20} MISMATCH — {len(unexplained)} unexplained: {sample}")
            else:
                print(f"  {store:<20} differs by reconciliation only "
                      f"({len(changed)} field(s)) — expected")

    # cross-file parity on shared stores
    print("\ncross-file parity (the guarantee the split provides):")
    shared = CFG["shared_stores"] + ["TOOLS"]
    for store in shared:
        a = normalise(parsed["index"].get(store))
        b = normalise(parsed["reference"].get(store))
        if a is None or b is None:
            continue
        ok = a == b
        if not ok:
            failures.append(f"parity.{store}")
        print(f"  {store:<20} {'identical' if ok else 'DIVERGENT'}")
    a = normalise(parsed["index"].get("SOURCES"))
    b = normalise(parsed["reference"].get("BIB"))
    if a is not None and b is not None:
        ok = a == b
        if not ok:
            failures.append("parity.SOURCES/BIB")
        print(f"  {'SOURCES / BIB':<20} {'identical' if ok else 'DIVERGENT'}")

    print(f"\n{len(failures)} failures" + (f": {failures}" if failures else ""))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
