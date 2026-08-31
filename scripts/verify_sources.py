#!/usr/bin/env python3
"""
verify_sources.py — check that every source resolves to the work it claims.

This targets the failure class that produced the Lincoln & Guba defect: a real,
resolvable DOI paired with a title that belongs to a different work. Nothing in
the tool surfaces that, because a working link looks identical to a correct one.

For each source with a DOI, the script asks Crossref what that DOI actually is
and compares the returned title against the citation text. Low overlap is
reported as a MISMATCH for human review.

    python3 scripts/verify_sources.py --dois          # DOI identity check
    python3 scripts/verify_sources.py --links         # HTTP reachability
    python3 scripts/verify_sources.py --dois --links --out review/link-report.json

Primo permalinks require an authenticated Lewis session and are reported as
SKIPPED rather than broken — an unauthenticated crawler cannot judge them.
Set a contact email in CONTACT: Crossref gives faster service to identified callers.
"""
import argparse
import json
import pathlib
import re
import sys
import time
import urllib.request
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTACT = "jbailey6@antioch.edu"
UA = f"LewisLibraryAITool/1.0 (mailto:{CONTACT})"
SKIP_HOSTS = ("i-share-lew.primo.exlibrisgroup.com", "primo.exlibrisgroup.com")

STOP = set("""a an the of and or for in on to with from by at as is are be this that
their its into using use guide handbook edition version journal review research""".split())


def load_sources():
    return json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(), r.geturl()


def tokens(text):
    return {w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in STOP}


def title_from_cite(cite):
    """Best-effort title extraction: the sentence after the year parenthesis."""
    m = re.search(r"\(\d{4}[a-z]?\)\.\s*(.+?)(?:\.\s|$)", cite or "")
    return m.group(1) if m else (cite or "")


def check_dois(sources, pause=0.2):
    results = []
    doi_sources = [(sid, r) for sid, r in sources.items()
                   if "doi.org/" in (r.get("url") or "")]
    print(f"checking {len(doi_sources)} DOI-bearing sources against Crossref")
    for sid, rec in doi_sources:
        doi = rec["url"].split("doi.org/", 1)[1].strip()
        entry = {"id": sid, "doi": doi, "status": None}
        resolved, registry = None, None
        # Crossref covers most publishers; DataCite covers Zenodo, figshare,
        # OSF and other repository DOIs. A DOI absent from one is normal.
        try:
            _, body, _ = get(f"https://api.crossref.org/works/{doi}")
            resolved = (json.loads(body)["message"].get("title") or [""])[0]
            registry = "crossref"
        except urllib.error.HTTPError as e:
            if e.code != 404:
                entry.update(status=f"crossref http {e.code}")
        except Exception as e:
            entry.update(status=type(e).__name__)
        if not resolved:
            try:
                _, body, _ = get(f"https://api.datacite.org/dois/{doi}")
                titles = json.loads(body)["data"]["attributes"].get("titles") or [{}]
                resolved = titles[0].get("title", "")
                registry = "datacite"
            except Exception:
                pass
        if resolved:
            claimed = title_from_cite(rec.get("cite", ""))
            a, b = tokens(claimed), tokens(resolved)
            overlap = len(a & b) / max(1, len(a))
            entry.update(status="ok", registry=registry, resolved_title=resolved,
                         claimed_title=claimed, overlap=round(overlap, 2),
                         verdict="match" if overlap >= 0.5 else "MISMATCH")
        else:
            entry.setdefault("status", "not found in crossref or datacite")
            entry["verdict"] = "unresolved"
        results.append(entry)
        flag = {"match": "  ", "MISMATCH": "!!", "unresolved": " ?", "error": " ?"}.get(
            entry.get("verdict"), " ?")
        print(f" {flag} {sid:<22} {entry.get('verdict','?'):<10} "
              f"overlap={entry.get('overlap','-')}")
        if entry.get("verdict") == "MISMATCH":
            print(f"      claimed : {entry['claimed_title'][:88]}")
            print(f"      resolves: {entry['resolved_title'][:88]}")
        time.sleep(pause)
    return results


def check_links(sources, pause=0.1):
    results = []
    print(f"\nchecking {len(sources)} source URLs")
    for sid, rec in sorted(sources.items()):
        url = rec.get("url") or ""
        entry = {"id": sid, "url": url}
        if not url:
            entry["verdict"] = "no url"
        elif any(h in url for h in SKIP_HOSTS):
            entry["verdict"] = "skipped (needs Lewis authentication)"
        else:
            try:
                code, _, final = get(url, timeout=25)
                entry.update(http=code, final_url=final,
                             redirected=(final.rstrip("/") != url.rstrip("/")),
                             verdict="ok" if code < 400 else f"http {code}")
            except urllib.error.HTTPError as e:
                entry.update(http=e.code, verdict=f"http {e.code}")
            except Exception as e:
                entry.update(verdict=f"unreachable ({type(e).__name__})")
            time.sleep(pause)
        results.append(entry)
        if entry["verdict"] not in ("ok",):
            print(f"    {sid:<22} {entry['verdict']}")
    ok = sum(1 for r in results if r.get("verdict") == "ok")
    print(f"  {ok} reachable, {len(results)-ok} skipped or needing review")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dois", action="store_true")
    ap.add_argument("--links", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--limit", type=int, help="check only the first N (for a quick pass)")
    args = ap.parse_args()
    if not (args.dois or args.links):
        ap.error("choose --dois and/or --links")

    sources = load_sources()
    if args.limit:
        sources = dict(list(sources.items())[:args.limit])

    report = {"checked": len(sources)}
    if args.dois:
        report["dois"] = check_dois(sources)
        bad = [r for r in report["dois"] if r.get("verdict") == "MISMATCH"]
        print(f"\n{len(bad)} DOI/title mismatches")
    if args.links:
        report["links"] = check_links(sources)

    if args.out:
        path = ROOT / args.out
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.out}")

    sys.exit(1 if args.dois and any(
        r.get("verdict") == "MISMATCH" for r in report.get("dois", [])) else 0)


if __name__ == "__main__":
    main()
