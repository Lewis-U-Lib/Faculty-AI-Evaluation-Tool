#!/usr/bin/env python3
"""
fix_can_support.py — repair the "can support" + bare infinitive construction.

Residue of the May 2026 rewrite, which converted "Use X to <verb>..." into
"X can support <verb>..." without adjusting the verb form. The correction
restores grammaticality while keeping the softened, non-directive register the
rewrite was aiming for:

    "Claude can support draft AI-use language"
    "Claude can help draft AI-use language"

Only the auxiliary is touched. Nothing else in the sentence is rewritten.

    python3 scripts/fix_can_support.py            # dry run
    python3 scripts/fix_can_support.py --apply
"""
import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "rules.json"

VERBS = ("scope draft build create design generate identify compare analyze write "
         "map test explore evaluate summarize translate check run produce").split()
PATTERN = re.compile(r"\bcan support (" + "|".join(VERBS) + r")\b")
FIELDS = ("desc", "instructions")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rules = json.loads(DATA.read_text(encoding="utf-8"))
    changes = []

    for rule in rules:
        for a in rule.get("activities", []):
            if not isinstance(a, dict):
                continue
            for field in FIELDS:
                text = a.get(field)
                if not isinstance(text, str) or not PATTERN.search(text):
                    continue
                fixed = PATTERN.sub(lambda m: f"can help {m.group(1)}", text)
                m = PATTERN.search(text)
                start = max(0, m.start() - 46)
                changes.append({
                    "title": a.get("title", "?"),
                    "field": field,
                    "before": text[start:m.end() + 46],
                    "after": fixed[start:m.end() + 44],
                })
                if args.apply:
                    a[field] = fixed

    for i, c in enumerate(changes, 1):
        print(f"{i:>2}. {c['title']}  [{c['field']}]")
        print(f"     - ...{c['before']}...")
        print(f"     + ...{c['after']}...")

    print(f"\n{len(changes)} correction(s)")
    if args.apply:
        DATA.write_text(json.dumps(rules, ensure_ascii=False, indent=1), encoding="utf-8")
        print("wrote data/rules.json — now run: ./publish.sh")
    else:
        print("dry run — re-run with --apply")


if __name__ == "__main__":
    main()
