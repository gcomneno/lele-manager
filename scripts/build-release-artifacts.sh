#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"

echo "==> Cleaning previous Python distribution outputs"
rm -rf     "$ROOT/build"     "$ROOT/dist"     "$ROOT/src/lele_manager.egg-info"

"$ROOT/scripts/build-gui.sh"

echo "==> Building sdist and wheel"
python -m build

echo "==> Checking distribution metadata"
python -m twine check "$ROOT"/dist/*

echo "OK: release artifacts available in $ROOT/dist"
