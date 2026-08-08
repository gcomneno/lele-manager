#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APP_NAME="LeLe-Manager"

echo "==> Building compiled GUI"
"$ROOT/scripts/build-gui.sh"

echo "==> Cleaning previous native bundle"
rm -rf "$ROOT/build/native" "$ROOT/dist/native"

echo "==> Building native application bundle"
python -m PyInstaller   --noconfirm   --clean   --onedir   --name "$APP_NAME"   --distpath "$ROOT/dist/native"   --workpath "$ROOT/build/native"   --specpath "$ROOT/build/native"   --collect-data lele_manager   "$ROOT/src/lele_manager/launcher.py"

echo
echo "OK: native application bundle:"
echo "    $ROOT/dist/native/$APP_NAME"
