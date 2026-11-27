#!/usr/bin/env bash
# Run all publisher checks on one catalogue CSV and write reports.
# usage: tools/run_checks.sh releases/<file>.csv reports/<name>
# Exit 0 only if part A (mirror of the app parser), part B (publisher checks) and pin integrity all pass.
# Status wording for any PR: "publisher checks passed; app validation pending".
set -u
csv="$1"; out="$2"; here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$out"
sha256sum "$csv" | tee "$out/sha256.txt"
python3 "$here/precheck_csv.py" "$csv" --json "$out/precheck.json"; pre=$?
python3 "$here/check_pins.py" "$csv" --json "$out/pins.json"; pins=$?
(cd "$here/estimation" && python3 estimate_csv.py "$OLDPWD/$csv" > "$OLDPWD/$out/estimates.txt" && cp estimates.json "$OLDPWD/$out/estimates.json"); est=$?
echo "precheck=$pre pins=$pins estimates=$est" | tee "$out/status.txt"
if [ $pins -eq 3 ]; then
  echo "RESULT: checks INCONCLUSIVE (Hub API errors/rate limits); no changes may be proposed; baseline kept" | tee -a "$out/status.txt"; exit 3
fi
if [ $pre -eq 0 ] && [ $pins -eq 0 ]; then
  echo "RESULT: publisher checks passed; app validation pending" | tee -a "$out/status.txt"; exit 0
else
  echo "RESULT: publisher checks FAILED (see precheck.json / pins.json); baseline must be kept" | tee -a "$out/status.txt"; exit 1
fi
