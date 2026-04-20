# Diagnostic Report — Faculty AI Evaluation Tool

Date: 2026-04-20 (UTC)
Repository: `Faculty-AI-Evaluation-Tool`
Scope reviewed: `index.html`, `Reference.html`

## What I validated

1. **JavaScript syntax integrity**
   - Extracted all inline `<script>` blocks and ran `node --check` against each.
   - Result: no syntax errors.

2. **DOM wiring sanity checks (static)**
   - Compared every `getElementById("...")` call against IDs present in markup.
   - Result: no missing IDs referenced by script.

3. **Rules/activities/source dataset consistency (static)**
   - Parsed the `RULES` JSON array and counted total entries and activities.
   - Counted source/tool entries in the catalog blocks.
   - Result: counts match published UI metadata:
     - Rules: **161**
     - Activities: **1,131**
     - Tools: **32**
     - Sources: **142**

4. **Internal-link validity**
   - Checked local (non-http) anchor targets in rendered HTML.
   - Found one broken local target:
     - `./index_audit_publication_polish.html` (file does not exist in repo)

5. **External/source URL reachability**
   - Attempted to validate URLs in `index.html` and `Reference.html` via HTTP HEAD/GET.
   - Environment limitation: outbound tunnel/proxy returned `403 Forbidden` for all tested domains, so source reachability could not be verified from this runtime.

6. **Feature-level logic review (static code path inspection)**
   - Carousel navigation (`prev/next`, step pill sync, auto-advance checks): logic present and event bindings intact.
   - Activity popup lifecycle (`open`, placement, close, outside click, escape): logic present and guarded.
   - Ask Us chat modal (`fabAskUs`, iframe lazy-load via `data-src`, close flows): logic present and guarded with fallback link.
   - Matching/recommendation engine:
     - Weighted score pipeline is deterministic for a given state unless user triggers reshuffle.
     - `Regenerate` intentionally introduces randomness via weighted sampling (`Math.random`).

---

## Issues found before implementing code changes

### 1) Broken local header link (high confidence)
- **Issue**: Header logo/title links to `./index_audit_publication_polish.html`, which is absent.
- **Impact**: Clicking title/logo yields a 404 in deployed site unless file exists outside repository.
- **Recommended fix** (pick one):
  1. Update href to `./index.html` (safe default), or
  2. Add/restore `index_audit_publication_polish.html` if intentionally separate.

### 2) Source validation cannot complete in current environment (high confidence)
- **Issue**: Network checks for source URLs are blocked by environment (`Tunnel connection failed: 403 Forbidden`).
- **Impact**: Unable to confirm live validity of bibliography links from here.
- **Recommended fix**:
  - Re-run URL validation in CI or a network-permissive environment (e.g., GitHub Action with curl/requests checks), and publish a dead-link report artifact.

### 3) Chat dependency observability gap (medium confidence)
- **Issue**: Chat iframe load success is not explicitly monitored; only fallback text/link is provided.
- **Impact**: Silent degradation possible if widget is blocked by CSP/X-Frame-Options/network.
- **Recommended fix**:
  - Add iframe `load`/timeout/error telemetry and show status indicator (e.g., “Chat connected” or “Chat unavailable — open separately”).

### 4) No automated browser regression suite for interaction-heavy UI (medium confidence)
- **Issue**: Interactions (carousel, popups, modal, copy/share, regenerate) are currently validated mostly by manual/static checks.
- **Impact**: Regressions can slip through during data or UI changes.
- **Recommended fix**:
  - Add Playwright smoke tests that verify:
    - carousel next/prev and page label,
    - option selection + result rendering threshold,
    - popup open/close + escape/outside click,
    - Ask Us modal opens/closes and iframe `src` assignment,
    - no console errors on initial load.

---

## Suggested pre-change gate (before feature edits)

Run this minimum checklist before any functional UI edits:
1. Static checks: JS parse + DOM ID reference scan.
2. Link checks: local links + external sources (in network-enabled CI).
3. Browser smoke tests: carousel/popup/modal/matching flow.
4. Data integrity checks: counts (tools/rules/activities/sources) match displayed metadata.


## Minimum checklist run (executed now)

Checklist status from this environment:

1. **Static checks: JS parse + DOM ID reference scan**
   - ✅ Completed.
   - Inline scripts parsed: **5/5 passed** (`node --check`).
   - `getElementById` references validated against markup IDs: **0 missing IDs**.

2. **Link checks: local links + external sources**
   - ⚠️ Partially completed.
   - Local link check: still **1 missing local target** (`./index_audit_publication_polish.html`).
   - External URL check: attempted with `curl -I` + `curl` fallback; blocked by proxy/tunnel (`403`, `curl: (56) CONNECT tunnel failed`), so live source validation remains pending for network-enabled CI.

3. **Browser smoke tests: carousel/popup/modal/matching flow**
   - ⚠️ Not executable in this runtime.
   - Attempted to run Playwright, but package retrieval was blocked (`npm E403` from registry), and no preinstalled browser automation runtime is available here.
   - Required follow-up: run smoke tests in CI where Playwright/browser dependencies are available.

4. **Data integrity checks: displayed metadata vs dataset counts**
   - ✅ Completed.
   - Computed from runtime data structures in `index.html`:
     - Tools: **32**
     - Rules: **161**
     - Activities: **1,131**
     - Sources: **142**
   - Displayed metadata text matches these values.

### Ready-before-edit fix queue (unchanged priorities)

1. Fix/remove broken local header link target.
2. Execute external source validation in network-enabled CI and capture report artifact.
3. Add browser smoke tests for carousel/popup/modal/matching flow.
4. Optionally add Ask Us iframe load/timeout telemetry for clearer operational status.
