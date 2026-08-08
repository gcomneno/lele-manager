#!/usr/bin/env bash

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="python"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    PYTHON_BIN="python3"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "ERRORE: Python non trovato."
else
    "$PYTHON_BIN" "$ROOT/scripts/build-native-app.py"
fi

printf '\nPrompt interattivo disponibile.\n'
