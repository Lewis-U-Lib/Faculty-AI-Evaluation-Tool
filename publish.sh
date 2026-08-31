#!/usr/bin/env bash
# publish.sh — the only command needed to produce deployable files.
# Validates canonical data, builds dist/, and refuses to publish on error.
set -euo pipefail
cd "$(dirname "$0")"
echo "== validate =="
python3 scripts/validate.py "$@"
echo
echo "== build =="
python3 scripts/build.py
echo
echo "dist/ is ready to publish. Do not edit files in dist/ — edit data/ and re-run."
