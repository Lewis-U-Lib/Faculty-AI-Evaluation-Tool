# Faculty AI Evaluation Tool — build repository

**Lewis University Library** · version 1.0.0

This repository holds the **source** of the Faculty AI Evaluation Tool and its Reference Guide. The published HTML files are generated from it.

The tool ships exactly as it always has: two self-contained HTML files, no server, no fetch, no CORS, works from `file://`, embeds in LibGuides unchanged. What changed is where the content lives while you work on it.

---

## Why this exists

Before the split, the corpus existed **twice** — 1.7 MB of byte-identical data in both `index.html` and `Reference.html`. Two copies that had to be edited together or would silently disagree.

They did disagree. The migration found `TOOLS.magicschool.desc` reading "teaching/course AI" in one file and "student-facing AI" in the other — a find-and-replace that ran against one and not the other, undetected. That is the third instance of the same failure class in this project's history, after the 119 drifted descriptions in May 2026 and the four corpus rollbacks in March.

There is now one copy. The build gives each page the shape its code expects, and `roundtrip_test.py` fails if the two ever diverge again.

---

## Quick start

```bash
./publish.sh          # validate, then build dist/
```

That is the whole publishing workflow. Upload `dist/index.html` and `dist/Reference.html`.

```bash
make validate         # checks only
make build            # build only
make review           # export CSVs for content review
make verify           # check every DOI and link
make test             # run the self-test
```

Requires Python 3 (standard library only) and, for `extract.py` and `roundtrip_test.py`, Node. No npm, no packages, no network except in `verify_sources.py`.

---

## The one rule

**Never edit anything in `dist/`.** It is generated output and your changes vanish on the next build. Every generated file carries a banner saying so. Edit `data/`, then rebuild.

---

## Layout

```
.github/workflows/        CI: validate + build + deploy to GitHub Pages
data/                     canonical source of truth — ONE copy, 1.9 MB
  rules.json                157 rules / 1,131 activities  (ordered array)
  sources.json              148 bibliography records      (keyed by id)
  tools.json                32 tools                      (keyed by id)
  origin_db.json            provenance records
  kw_sources.json           keyword -> source mapping
  rule_fallback.json        rule-prefix -> source fallback
  bloom_src.json            Bloom-level -> source fallback
  specimens.json            25 teaching specimens
  syllabus_spectrum.json    policy spectrum
  origin_type_links.json    provenance type links
  _provenance.json          which published file each store came from

templates/                page shells with data replaced by inert markers
  index.template.html       522 KB
  reference.template.html   412 KB

scripts/
  extract.py                one-time migration: published HTML -> data/ + templates/
  reconcile.py              merge divergent stores into one canonical record
  validate.py               schema, integrity, editorial checks — gates publishing
  build.py                  data/ + templates/ -> dist/
  roundtrip_test.py         proves the build preserves meaning and parity holds
  review.py                 CSV export/import for spreadsheet content review
  verify_sources.py         DOI identity and link health against Crossref/DataCite
  selftest.py               proves the validator still catches historical defects
  fix_can_support.py        one-off content repair (already applied in 1.0)

dist/                     generated — do not edit, not in version control
build.json                build configuration: targets, stores, shapes
publish.sh                validate + build
DEPLOYMENT.md             GitHub Pages migration roadmap
```

See **DEPLOYMENT.md** for moving this repository onto GitHub Pages with
Actions. Published URLs do not change; validation gates every deploy.

### The marker convention

Each externalised store appears in the template as:

```javascript
var RULES = /*@@RULES@@*/null;
```

This stays valid JavaScript, so a template can be opened, linted, and diffed on its own without the build having run.

### Shapes

`index.html` wants `SOURCES` and `TOOLS` as objects keyed by id. `Reference.html` wants `BIB` and `TOOLS` as arrays carrying an `id` field. One canonical record, two serialisations, declared in `build.json` under `shapes`.

`RULES` is an **ordered array** and is never re-keyed — rule order drives matching priority. This is declared explicitly in `build.json` under `id_keyed` rather than inferred, because rules also carry unique ids and an inferring extractor silently converts them.

---

## Everyday tasks

**Fix a typo in an activity**
Edit `data/rules.json`, then `./publish.sh`.

**Add a source**
Add one record to `data/sources.json`. It reaches both files automatically — index gets it in `SOURCES`, the guide gets it in `BIB`. There is no second place to update.

**Send activities out for review**
```bash
make review                                          # writes review/activities.csv
# reviewers edit in Excel or Sheets, filling reviewed_by / reviewed_on / review_note
python3 scripts/review.py import --file review/activities.csv          # dry run
python3 scripts/review.py import --file review/activities.csv --apply
./publish.sh
```
Import is keyed on `rule_id` + `title`, reports unmatched rows rather than guessing, and refuses to change those key fields.

**Check the bibliography**
```bash
python3 scripts/verify_sources.py --dois --links --out review/link-report.json
```
`--dois` asks Crossref (and DataCite for Zenodo-style DOIs) what each identifier actually is and compares the resolved title against the citation. This is the check that catches a real DOI attached to the wrong work — the defect found in August 2026, where a link labelled "Lincoln & Guba — Naturalistic Inquiry" resolved to a 2000 article by a different author. Primo permalinks are reported as skipped, since an unauthenticated crawler cannot judge them.

---

## Validation

`validate.py` runs before every build and exits non-zero on any error.

**Errors** (block publishing): activities missing a required field, duplicate activity titles, source ids referenced but undefined, rules with no activities, malformed source URLs.

**Warnings** (reported, do not block): the malformed "can support" + infinitive construction, known copy errors, unqualified efficacy language, metadata coverage below 100%, sources defined but never referenced.

Use `--strict` to promote warnings to errors once the current batch is cleared, so they cannot reappear.

Current state:

```
rules=157  activities=1131  sources=148
  tier       1131/1131 (100%)
  mode       1131/1131 (100%)
  bloom      1131/1131 (100%)
0 errors, 1 warning
```

The remaining warning covers 37 bibliography records that are not yet referenced by the per-activity mapping layers. They remain available in the full Sources tab while their activity-level relationships are reviewed. The 2026-08-31 activity audit resolved the copy error and efficacy-language backlog. Existing `arch` values are retained as editorial history, but `arch` is not consumed by either runtime and is no longer treated as required coverage.

### What the guards would have caught

`selftest.py` injects real historical failures and asserts the validator rejects each one:

| Defect | When it happened | Detected then | Caught now |
|---|---|---|---|
| Duplicate activity titles | Mar 26, 2026 | Aug 13 — five months later | yes |
| Corpus rollback to 500 activities | Mar 27 and Mar 30, four episodes | manually, same day | yes |
| Dangling source id | risk of any key rename | not checked | yes |
| Activity missing a required field | — | not checked | yes |
| Cross-file drift | May 2026, 119 descriptions | Aug audit — three months | yes, via `roundtrip_test.py` |

---

## Verification performed on this build

| Check | Result |
|---|---|
| Data stores round-tripped, index | 10 of 10 preserved |
| Data stores round-tripped, guide | 10 of 10 preserved |
| Cross-file parity | 10 shared stores, 0 divergent |
| `validate.py` | 0 errors, 1 warning |
| `selftest.py` | 5 of 5 defect classes caught |
| DOI identity, all 16 DOI-bearing sources | 16 resolve, 0 mismatches |
| Built files in Chromium | 0 page errors, both |
| Modal close paths | specimen, chat, disclosure all pass |
| Button count, index | 122, unchanged from source |

Two stores differ from the pre-split originals by design, and the round-trip test classifies them as expected rather than failures: `SOURCES` gained the `access` field that previously existed only in `BIB`, and `TOOLS` took the resolved value for the magicschool divergence.

---

## Known editorial decisions carried forward

**`TOOLS.magicschool.desc`** — index said "teaching/course AI", the guide said "student-facing AI". The index value was kept pending a decision. Change it in `data/tools.json` if the other is correct; it now propagates to both files from one edit.

**Twelve malformed descriptions — FIXED in 1.0.** "can support draft", "can support scope" and similar, residue of the May 2026 rewrite that converted "Use X to *verb*" without adjusting the verb form. All twelve now read "can help <verb>", which restores grammaticality while keeping the softened, non-directive register the rewrite intended. Applied by `scripts/fix_can_support.py`; `validate.py` still guards against the construction returning.

**One copy error — FIXED.** "What would you can ask the original authors?" in *Experimental Replication Feasibility Assessment* now reads "What could you ask the original authors?" `validate.py` continues to guard against the error returning.

**A find-and-replace artifact appears three times** — a substitution of "student-facing" with "teaching/course" that leaves the sentence odd: `TOOLS.magicschool.desc`, *Syllabi Language Workshop* ("formal, conversational, and teaching/course plain language"), and *AI-Assisted Rubric Design Workshop* ("discipline-specific criteria, teaching/course language"). All three read as though the intended word was "student-facing". Not changed — editorial call.

**`arch` metadata retained, not required.** Existing values remain available for editorial history. Because neither runtime consumes `arch`, it is not part of the required schema or coverage gate.

---

## Notes

Serialising through canonical JSON also repaired the invalid-JSON defect introduced at version 5.7, where a `\'` escape inside an `instructions` string made `RULES` fail a strict JSON parse while remaining valid JavaScript. `data/rules.json` is valid JSON and the build emits valid JSON into both pages.

`build.json` carries the version number. Bump it there; it appears in the banner of every generated file alongside a content digest, so a published page can be traced to the exact data that produced it.
