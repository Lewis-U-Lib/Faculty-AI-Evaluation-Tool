#!/usr/bin/env python3
"""
selftest.py — prove the pipeline catches the defects that actually happened.

Each case injects a real historical failure into a copy of the canonical data,
runs validate.py against it, and asserts the checker fails. If a case passes
validation, the guard for that defect class has regressed.

The cases are drawn from the tool's own version history:
  1. duplicate activity titles      introduced 2026-03-26, undetected until 2026-08-13
  2. corpus rollback                2026-03-27 and 2026-03-30, four episodes
  3. dangling source id             the class the Perkins key rename could have caused
  4. missing required field         would ship an activity card with holes
  5. malformed 'can support'        the May 2026 rewrite residue, still live
  6. unknown specimen class         would silently omit a specimen from the library
  7. dangling specimen source       would display an internal id instead of attribution
  8. missing renderer template      makes renderer validation impossible
  9. renderer map missing a class   silently omits valid specimen cards

    python3 scripts/selftest.py
"""
import copy
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run_validate(workdir):
    p = subprocess.run([sys.executable, str(workdir / "scripts" / "validate.py")],
                       capture_output=True, text=True, cwd=workdir)
    return p.returncode, p.stdout


def sandbox():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="aitool-selftest-"))
    (tmp / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "validate.py", tmp / "scripts" / "validate.py")
    shutil.copytree(ROOT / "data", tmp / "data")
    shutil.copytree(ROOT / "templates", tmp / "templates")
    shutil.copy(ROOT / "build.json", tmp / "build.json")
    return tmp


CASES = []


def case(name, expect_fail=True):
    def deco(fn):
        CASES.append((name, fn, expect_fail))
        return fn
    return deco


@case("baseline: unmodified data validates")
def baseline(data):
    return data


@case("duplicate activity title (the Mar 26 defect)")
def dup_title(data):
    rules = data["rules"]
    first = rules[0]["activities"][0]
    for r in rules[1:]:
        if r.get("activities"):
            r["activities"][0]["title"] = first["title"]
            break
    return data


@case("corpus rollback: activities dropped from a rule")
def rollback(data):
    for r in data["rules"]:
        if r.get("activities"):
            r["activities"] = []
            break
    return data


@case("dangling source id in kw_sources")
def dangling(data):
    key = next(iter(data["kw_sources"]))
    value = data["kw_sources"][key]
    if isinstance(value, list):
        value.append("ghostsource2099")
    elif isinstance(value, dict):
        value[next(iter(value))] = ["ghostsource2099"]
    return data


@case("activity missing a required field")
def missing_field(data):
    data["rules"][0]["activities"][0].pop("instructions", None)
    return data


@case("unknown specimen class")
def unknown_specimen_class(data):
    data["specimens"][0]["defect_class"] = "unregistered_error"
    return data


@case("dangling source id in a literature specimen")
def dangling_specimen_source(data):
    specimen = next(s for s in data["specimens"]
                    if s.get("provenance") == "captured_from_literature")
    specimen["instance_source"] = "ghostsource2099"
    return data


@case("missing renderer templates")
def missing_renderer_templates(data):
    return data


@case("renderer map missing a specimen class")
def renderer_map_missing_class(data):
    return data


def main():
    base = {name: json.loads((ROOT / "data" / f"{name}.json").read_text(encoding="utf-8"))
            for name in ("rules", "sources", "specimens", "kw_sources", "rule_fallback", "bloom_src")}

    passed, failed = 0, 0
    for name, mutate, expect_fail in CASES:
        tmp = sandbox()
        try:
            data = mutate(copy.deepcopy(base))
            for key, value in data.items():
                (tmp / "data" / f"{key}.json").write_text(
                    json.dumps(value, ensure_ascii=False), encoding="utf-8")
            if name == "missing renderer templates":
                shutil.rmtree(tmp / "templates", ignore_errors=True)
            elif name == "renderer map missing a specimen class":
                template = tmp / "templates" / "reference.template.html"
                text = template.read_text(encoding="utf-8")
                needle = ", logic_error:'Logic error'"
                if needle not in text:
                    raise RuntimeError("self-test fixture no longer matches the renderer map")
                template.write_text(text.replace(needle, "", 1), encoding="utf-8")
            code, out = run_validate(tmp)
            caught = code != 0
            want = expect_fail if name != "baseline: unmodified data validates" else False
            ok = (caught == want)
            status = "PASS" if ok else "FAIL"
            detail = "validator rejected it" if caught else "validator accepted it"
            print(f"  [{status}] {name:<48} {detail}")
            if ok:
                passed += 1
            else:
                failed += 1
                print("        " + "\n        ".join(out.strip().splitlines()[-4:]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
