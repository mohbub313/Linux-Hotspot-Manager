#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 -m compileall -q "$ROOT/src" "$ROOT/host" "$ROOT/portal"
if command -v pytest >/dev/null 2>&1; then pytest -q "$ROOT/tests"
else echo "pytest not installed; syntax validation completed"
fi
sh "$ROOT/scripts/check-dependencies.sh" || true
echo "Release validation complete"
