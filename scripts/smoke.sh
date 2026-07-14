#!/usr/bin/env bash
# Smoke test for tablegold: run the example pipeline demo, then exercise the
# real CLI end to end — bless, show, diff (match, tolerance, key alignment,
# drift, JSON) — asserting on outputs and exit codes.
# Self-contained: pure stdlib, no network, idempotent (works from a clean tree).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

# The package has zero runtime dependencies, so running from src/ needs no install.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/tablegold-smoke.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

echo "[smoke] python: $("$PYTHON" --version 2>&1)"

# 1. The example pipeline: fold-order noise passes, the regression is caught.
demo_out="$("$PYTHON" "$ROOT/examples/pipeline_demo.py" "$WORKDIR/demo")" \
  || fail "pipeline_demo.py exited non-zero"
echo "$demo_out" | sed 's/^/[demo] /'
echo "$demo_out" | grep -q "fold-order noise vs golden: MATCH" \
  || fail "float noise was not tolerated"
echo "$demo_out" | grep -q "discount change vs golden: MISMATCH" \
  || fail "the regression was not caught"
echo "$demo_out" | grep -q "DEMO OK" || fail "demo did not finish"

# 2. bless: canonicalize an actual file into a golden.
printf 'id,region,revenue\n1002,west,88.25\n1001,east,100.5\n' > "$WORKDIR/actual.csv"
bless_out="$("$PYTHON" -m tablegold bless "$WORKDIR/actual.csv" "$WORKDIR/golden.csv")"
echo "$bless_out" | grep -q "blessed .*golden.csv (2 row(s), 3 column(s))" \
  || fail "bless did not report the blessed shape"

# 3. show: schema inference on the blessed golden.
show_out="$("$PYTHON" -m tablegold show "$WORKDIR/golden.csv")"
echo "$show_out" | sed 's/^/[show] /'
echo "$show_out" | grep -q "rows: 2" || fail "show missing row count"
echo "$show_out" | grep -Eq 'revenue +float' || fail "show did not infer revenue as float"

# 4. diff: identical file matches with exit 0.
"$PYTHON" -m tablegold diff "$WORKDIR/golden.csv" "$WORKDIR/actual.csv" >/dev/null \
  || fail "diff of blessed vs source should exit 0"

# 5. diff: float noise + reordered rows match under --key (exit 0).
printf 'id,region,revenue\n1001,east,100.50000000001\n1002,west,88.25\n' > "$WORKDIR/noisy.csv"
"$PYTHON" -m tablegold diff --key id --rtol 1e-9 "$WORKDIR/golden.csv" "$WORKDIR/noisy.csv" >/dev/null \
  || fail "sub-tolerance noise with key alignment should exit 0"

# 6. diff: real drift exits 1 and the report names the cell.
printf 'id,region,revenue\n1001,east,100.5\n1002,west,90.25\n' > "$WORKDIR/drifted.csv"
set +e
diff_out="$("$PYTHON" -m tablegold diff --key id "$WORKDIR/golden.csv" "$WORKDIR/drifted.csv")"
diff_rc=$?
set -e
echo "$diff_out" | sed 's/^/[diff] /'
[ "$diff_rc" -eq 1 ] || fail "diff on drift should exit 1, got $diff_rc"
echo "$diff_out" | grep -q "id=1002: golden=88.25 actual=90.25" \
  || fail "diff did not pinpoint the drifted cell"
echo "$diff_out" | grep -q "result: MISMATCH" || fail "diff did not report MISMATCH"

# 7. diff --format json: machine report is valid JSON with the right verdict.
set +e
json_out="$("$PYTHON" -m tablegold diff --format json --key id "$WORKDIR/golden.csv" "$WORKDIR/drifted.csv")"
set -e
echo "$json_out" | "$PYTHON" -c '
import json, sys
payload = json.load(sys.stdin)
assert payload["ok"] is False, "json ok flag"
assert payload["cell_diffs"]["total"] == 1, "json diff count"
' || fail "JSON report was invalid or wrong"

# 8. --version agrees with the package version.
version_out="$("$PYTHON" -m tablegold --version)"
pkg_version="$("$PYTHON" -c 'import tablegold; print(tablegold.__version__)')"
[ "$version_out" = "tablegold $pkg_version" ] \
  || fail "--version mismatch: '$version_out' vs package '$pkg_version'"
"$PYTHON" -m tablegold --help | grep -q "bless" || fail "--help missing bless command"

echo "SMOKE OK"
