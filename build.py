#!/usr/bin/env python3
"""
build.py — canonical data/ + templates/  ->  deployable single-file HTML in dist/

The output is byte-for-byte publishable: self-contained, no fetch(), no CORS,
works from file://. Deployment is unchanged from the pre-split tool.

Each target receives each store in the shape its own code expects (see
build.json "shapes"): index wants SOURCES and TOOLS as objects keyed by id;
Reference wants BIB and TOOLS as arrays carrying an id field. One canonical
record, two serialisations.

Usage:
    python3 scripts/build.py                 # build all targets
    python3 scripts/build.py --target index  # build one
    python3 scripts/build.py --check         # build to memory, report, write nothing
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "build.json").read_text(encoding="utf-8"))
MARKER = re.compile(r"/\*@@(\w+)@@\*/null")

BANNER = """<!--
  GENERATED FILE — DO NOT EDIT.
  Produced by scripts/build.py from data/ + {template}
  Any edit made here is lost on the next build. Edit data/ instead, then rebuild.
  {project} {version} · built {stamp} · data {digest}
-->"""


def load(name):
    path = ROOT / "data" / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"missing data file: data/{name}.json")
    return json.loads(path.read_text(encoding="utf-8"))


def as_array(obj):
    if isinstance(obj, list):
        return obj
    return [dict(id=k, **v) for k, v in obj.items()]


def as_object(value):
    if isinstance(value, dict):
        return value
    return {x["id"]: {k: v for k, v in x.items() if k != "id"} for x in value}


def data_digest():
    """Stable short hash over all canonical data — identifies the content build."""
    h = hashlib.sha256()
    for path in sorted((ROOT / "data").glob("*.json")):
        if path.name.startswith("_"):
            continue
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:12]


def build(target, digest, write=True):
    template_path = ROOT / target["template"]
    if not template_path.exists():
        raise SystemExit(f"missing template: {target['template']}")
    html = template_path.read_text(encoding="utf-8")

    seen, missing = [], []

    def substitute(m):
        store = m.group(1)
        datafile = target["stores"].get(store)
        if not datafile:
            missing.append(store)
            return m.group(0)
        value = load(datafile)
        shape = target.get("shapes", {}).get(store)
        if shape == "array":
            value = as_array(value)
        elif shape == "object":
            value = as_object(value)
        seen.append(store)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    html = MARKER.sub(substitute, html)

    if missing:
        raise SystemExit(f"{target['name']}: markers with no data mapping: {missing}")
    leftover = MARKER.findall(html)
    if leftover:
        raise SystemExit(f"{target['name']}: unreplaced markers: {leftover}")

    banner = BANNER.format(
        template=target["template"], project=CFG["project"],
        version=CFG["version"], digest=digest,
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
    html = re.sub(r"(<!doctype html>)", r"\1\n" + banner, html,
                  count=1, flags=re.IGNORECASE)

    out = ROOT / "dist" / target["output"]
    if write:
        out.parent.mkdir(exist_ok=True)
        out.write_text(html, encoding="utf-8")
    return html, seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target")
    ap.add_argument("--check", action="store_true",
                    help="build without writing; useful in CI or pre-commit")
    args = ap.parse_args()

    targets = [t for t in CFG["targets"] if not args.target or t["name"] == args.target]
    if not targets:
        raise SystemExit(f"no such target: {args.target}")

    digest = data_digest()
    print(f"{CFG['project']} {CFG['version']} · data digest {digest}")
    manifest = {"version": CFG["version"], "data_digest": digest,
                "built": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "outputs": {}}

    for t in targets:
        html, seen = build(t, digest, write=not args.check)
        manifest["outputs"][t["output"]] = {
            "bytes": len(html.encode("utf-8")),
            "stores": len(seen),
            "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest()[:16],
        }
        verb = "would write" if args.check else "wrote"
        print(f"  {verb} dist/{t['output']:<18} {len(html)/1024:>7.0f} KB  "
              f"{len(seen)} stores inlined")

    if not args.check:
        (ROOT / "dist" / "build-manifest.json").write_text(
            json.dumps(manifest, indent=1), encoding="utf-8")
        print("  wrote dist/build-manifest.json")


if __name__ == "__main__":
    main()
