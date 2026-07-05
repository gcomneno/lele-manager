#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"
TARGET="$ROOT/src/lele_manager/gui/static"

echo "==> Building LeLe Manager GUI (Vite + Svelte)"
cd "$FRONTEND"

if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi

npm run build

echo "==> Copying dist → src/lele_manager/gui/static"
rm -rf "$TARGET"
mkdir -p "$TARGET"
cp -r dist/* "$TARGET/"

echo "OK: GUI build in $TARGET"
