# Deploying to GitHub Pages

**Faculty AI Evaluation Tool 1.0 · Lewis University Library**
Migration roadmap for `Lewis-U-Lib/Faculty-AI-Evaluation-Tool`

---

## The constraint that governs everything

**Published URLs must not change.** The tool is embedded in LibGuides and linked from faculty communications. Whatever the repository looks like internally, these must keep resolving:

```
https://lewis-u-lib.github.io/Faculty-AI-Evaluation-Tool/index.html
https://lewis-u-lib.github.io/Faculty-AI-Evaluation-Tool/Reference.html
```

The plan below preserves them exactly. `dist/` is published *as the site root*, so `dist/index.html` becomes `/Faculty-AI-Evaluation-Tool/index.html` — the same address it has today. Nothing embedded, bookmarked, or linked breaks.

Verify this before switching anything: `Reference.html` must keep its capital R. GitHub Pages is case-sensitive, and the tool links to `Reference.html` from inside `index.html`.

---

## What changes, and what doesn't

| | Before | After |
|---|---|---|
| Published URLs | unchanged | **unchanged** |
| What visitors download | one self-contained HTML file | **one self-contained HTML file** |
| Works offline / from `file://` | yes | **yes** |
| LibGuides embedding | unchanged | **unchanged** |
| What lives in the repo root | the built HTML | source: `data/`, `templates/`, `scripts/` |
| How publishing happens | upload a file through the browser | commit; Actions validates and deploys |
| What happens to a bad edit | it goes live | **the build fails and nothing deploys** |

That last row is the point of the exercise. Today nothing sits between a mistaken upload and faculty. After this, a duplicate title, a dangling source id, a missing field, or a corpus rollback stops the deployment.

---

## Phase 1 — Prepare the repository

The repository currently serves `index.html` and `Reference.html` from the root of `main`. Those files become build *output* — but **do not remove them yet**. Removing them before Pages is building from Actions would leave the live site returning 404 to faculty in the gap between the two steps. They are ignored once Actions is serving the site, so they cost nothing by remaining until you have verified the new path.

**Before touching anything, tag the current state** so there is a labelled point to return to:

```
git tag pre-split-2026-08-31
git push origin pre-split-2026-08-31
```

Then commit the 1.0 repository contents into `main`:

```
data/                     canonical data
templates/                page shells
scripts/                  build, validate, review, verify
.github/workflows/        the three workflows below
build.json  publish.sh  Makefile  README.md  .gitignore
```

and remove `index.html` and `Reference.html` from the root in the same commit.

Removing them does not destroy anything. All 406 commits of history remain reachable — `git log --follow -- index.html` still works after the file is gone, and the tagged commit above still contains the exact bytes currently published.

`.gitignore` already excludes `dist/`. Built files are never committed; they are produced on every deploy.

**The one rule, restated because it is the only way this goes wrong:** never edit files in `dist/`. They are generated, and the next build overwrites them.

---

## Phase 2 — Switch Pages to build from Actions

In the repository: **Settings → Pages → Build and deployment → Source**, change from *Deploy from a branch* to **GitHub Actions**.

This is the switch that matters. Until you flip it, Pages keeps serving whatever is on the branch; after you flip it, Pages serves what the workflow uploads.

Three workflows are included.

**`deploy.yml`** — runs on every push to `main` that touches `data/`, `templates/`, `scripts/`, or `build.json`. It validates, runs the self-test, builds, adds `.nojekyll`, confirms both files are non-empty, and publishes `dist/` as the site. If validation fails, the deploy job never runs and the live site is untouched.

**`check-pull-request.yml`** — runs the same checks on pull requests plus a cross-file parity assertion, and publishes nothing. This is how a colleague proposes a change safely.

**`check-sources.yml`** — monthly. Re-resolves every DOI against Crossref and DataCite, checks that each still matches its claimed title, tests public links, and opens an issue if anything needs review. Primo permalinks are skipped, since an unauthenticated runner cannot judge them.

Only `deploy.yml` needs Python. The PR check also uses Node for the parity assertion.

**Action versions.** All pins target Node 24. GitHub removes Node 20 from its runners on **September 16, 2026**, and anything still pinned to a Node 20 action will fail after that date rather than merely warn. Current pins: `checkout@v7`, `setup-python@v7`, `setup-node@v7`, `upload-artifact@v7`, `configure-pages@v6`, `upload-pages-artifact@v5`, `deploy-pages@v5`, `github-script@v9`. If a run ever reports a Node 20 deprecation again, the fix is to bump the named action to its current major — the warning always names the offender.

`.nojekyll` is added by the workflow rather than committed, so Pages does not run the files through Jekyll.

---

## Phase 3 — Verify before you trust it

Run the deploy once with **Actions → Build and deploy → Run workflow**, then check each of these against the live site:

1. Both URLs load and render. Confirm the capital R on `Reference.html`.
2. `index.html` links through to the guide and the link resolves.
3. The Sources tab shows **144** — that is correct, not a bug. Four entries are flagged `retired` and excluded from the count; there are 148 records.
4. Open the Specimen Library and close it three ways: the ✕, a click on the backdrop, and Escape. All three must work; this regressed once before.
5. View source on the deployed page. The top of the file should read `GENERATED FILE — DO NOT EDIT` with a version and data digest. Confirm the digest matches `dist/build-manifest.json` from the workflow run.
6. Load the LibGuides page that embeds the tool and confirm it still renders.
7. Save the page to your desktop and open it from `file://`. It must still work — that is the property runtime fetching would have cost you.

If anything fails, Phase 6 gets you back.

---

## Phase 4 — Everyday editing after the switch

**A small content fix, no terminal.** Open `data/rules.json` in GitHub's web editor, make the change, commit to `main`. Actions validates and deploys in a couple of minutes. If validation fails you get an email and the live site is unchanged. This preserves the browser-based workflow you already use while adding the checks that were missing.

Note that `rules.json` is 1.4 MB, which the web editor handles but not comfortably. For anything larger than a typo, prefer the next two paths.

**A batch of content edits.** Export to CSV, review in Excel, import back:

```
make review
# reviewers edit review/activities.csv, filling reviewed_by / reviewed_on / review_note
python3 scripts/review.py import --file review/activities.csv          # dry run
python3 scripts/review.py import --file review/activities.csv --apply
./publish.sh                                                            # confirm locally
git commit -am "Content review: <what changed>" && git push
```

**A change from a colleague.** They fork or branch, edit `data/`, open a pull request. `check-pull-request.yml` validates and reports. Merge deploys.

**Adding a source.** One record in `data/sources.json`. It reaches both files automatically. There is no second place to update, and the parity check enforces that.

---

## Phase 5 — Optional, once the basics are steady

**Branch protection.** Require the PR check to pass before merging to `main`. Settings → Branches → add a rule for `main` → require status checks.

**Strict mode.** Once the remaining warnings are cleared, change the deploy step to `python3 scripts/validate.py --strict` so warnings block publication and cannot creep back.

**A staging copy.** A second Pages site from a `staging` branch lets you preview a large content change at a real URL before it reaches faculty.

**Version visibility.** The build already stamps every file with a version and data digest in an HTML comment. Surfacing that in the interface footer would address the audit's recommendation that content version and bibliography version be visible together — a small template edit.

---

## Phase 6 — Rollback

Three levels, fastest first.

**Undo the last change.** Revert the commit and push. Actions rebuilds and redeploys from the previous data. Roughly two minutes.

**Redeploy a known-good build.** Actions → Build and deploy → Run workflow, selecting an earlier commit.

**Return to the pre-split state entirely.** Settings → Pages → Source → back to *Deploy from a branch*, then restore `index.html` and `Reference.html` to the root from the tag created in Phase 1:

```
git checkout pre-split-2026-08-31 -- index.html Reference.html
git commit -m "Restore pre-split published files" && git push
```

The old files are never more than one command away, which is why the tag is worth creating before anything else.

---

## What to watch for

**Case sensitivity.** GitHub Pages is case-sensitive; your desktop probably is not. `Reference.html` must keep its capital R or the in-tool link breaks only after deployment.

**Deploy latency.** A push takes a minute or two to appear, and browsers may hold the old file. Hard-refresh before concluding something failed.

**Repository size.** `data/` is 1.9 MB and `rules.json` changes often, so history will grow. This is well within normal limits, but avoid committing `dist/` — that would add 4.4 MB per publish.

**Actions minutes.** Public repositories get them free. If the repository is ever made private, the monthly allowance applies.

**The discipline requirement.** Every generated file carries a do-not-edit banner. The failure mode is someone hotfixing `dist/` under time pressure and losing it on the next build. The banner is the mitigation; awareness is the rest of it.

---

## Sequence, condensed

| Step | Action | Reversible |
|---|---|---|
| 1 | Tag the current published state | — |
| 2 | Commit 1.0 source — **leave the root HTML in place** | yes, via tag |
| 3 | Settings → Pages → Source → GitHub Actions | yes, one setting |
| 4 | Run the deploy workflow manually | yes |
| 5 | Work the Phase 3 verification list | — |
| 6 | Confirm the LibGuides embed still renders | — |
| 7 | **Now** remove `index.html` and `Reference.html` from the root | yes, via tag |
| 8 | Enable branch protection and strict mode | yes |

The "Build and deploy" entry does not appear under Actions until `deploy.yml` exists on the **default branch**. Actions only lists workflows it finds in `main`, so step 2 must land before step 4 is possible.

Steps 1 through 4 are perhaps an hour. Step 5 is the part worth not rushing.
