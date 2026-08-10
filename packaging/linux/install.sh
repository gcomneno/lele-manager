#!/usr/bin/env bash
# Install the extracted Linux native release into stable user-local paths.

set -euo pipefail

APP_NAME="LeLe-Manager"
PRODUCT_NAME="lele-manager"

fail() {
    printf 'ERRORE: %s\n' "$*" >&2
    exit 1
}

require_absolute_path() {
    case "$1" in
        /*) ;;
        *) fail "$2 deve essere un percorso assoluto: $1" ;;
    esac
}

require_safe_directory() {
    local path="$1"
    local label="$2"

    if [ -L "$path" ]; then
        fail "$label non deve essere un link simbolico: $path"
    fi
    if [ -e "$path" ] && [ ! -d "$path" ]; then
        fail "$label non e' una directory: $path"
    fi

    mkdir -p "$path"

    if [ -L "$path" ] || [ ! -d "$path" ]; then
        fail "$label non e' una directory sicura: $path"
    fi
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_BUNDLE="$SCRIPT_DIR/$APP_NAME"
SOURCE_EXECUTABLE="$SOURCE_BUNDLE/$APP_NAME"

[ -d "$SOURCE_BUNDLE" ] || fail "bundle nativo assente: $SOURCE_BUNDLE"
[ -f "$SOURCE_EXECUTABLE" ] || fail "eseguibile nativo assente: $SOURCE_EXECUTABLE"
[ -x "$SOURCE_EXECUTABLE" ] || fail "eseguibile nativo non eseguibile: $SOURCE_EXECUTABLE"

if [ -n "${XDG_DATA_HOME:-}" ]; then
    DATA_HOME="$XDG_DATA_HOME"
else
    [ -n "${HOME:-}" ] || fail "HOME non e' impostata"
    DATA_HOME="$HOME/.local/share"
fi
require_absolute_path "$DATA_HOME" "XDG_DATA_HOME"

if [ -n "${LELE_MANAGER_INSTALL_BIN_DIR:-}" ]; then
    BIN_DIR="$LELE_MANAGER_INSTALL_BIN_DIR"
else
    [ -n "${HOME:-}" ] || fail "HOME non e' impostata"
    BIN_DIR="$HOME/.local/bin"
fi
require_absolute_path "$BIN_DIR" "la directory bin di installazione"

PRODUCT_ROOT="$DATA_HOME/$PRODUCT_NAME"
INSTALL_ROOT="$PRODUCT_ROOT/install"
APP_DIR="$INSTALL_ROOT/app"
APP_EXECUTABLE="$APP_DIR/$APP_NAME"
LAUNCHER="$BIN_DIR/$PRODUCT_NAME"

require_safe_directory "$INSTALL_ROOT" "la radice di installazione"
require_safe_directory "$BIN_DIR" "la directory bin di installazione"

if [ -L "$APP_DIR" ]; then
    fail "la directory app installata non deve essere un link simbolico: $APP_DIR"
fi
if [ -e "$APP_DIR" ] && [ ! -d "$APP_DIR" ]; then
    fail "la directory app installata non e' una directory: $APP_DIR"
fi

if [ -L "$LAUNCHER" ]; then
    launcher_target="$(readlink "$LAUNCHER")"
    [ "$launcher_target" = "$APP_EXECUTABLE" ] || fail \
        "il launcher esistente non appartiene a LeLe Manager: $LAUNCHER"
elif [ -e "$LAUNCHER" ]; then
    fail "il launcher esistente non appartiene a LeLe Manager: $LAUNCHER"
fi

STAGING_DIR="$(mktemp -d "$INSTALL_ROOT/.app-staging.XXXXXX")"
BACKUP_DIR=""
cleanup() {
    local status=$?
    if [ -n "${STAGING_DIR:-}" ] && [ -d "$STAGING_DIR" ]; then
        rm -rf "$STAGING_DIR"
    fi
    exit "$status"
}
trap cleanup EXIT

cp -a "$SOURCE_BUNDLE" "$STAGING_DIR/app"
STAGED_EXECUTABLE="$STAGING_DIR/app/$APP_NAME"
[ -f "$STAGED_EXECUTABLE" ] || fail "copia staged senza eseguibile nativo"
[ -x "$STAGED_EXECUTABLE" ] || fail "copia staged senza eseguibile nativo eseguibile"

if [ -d "$APP_DIR" ]; then
    BACKUP_DIR="$(mktemp -d "$INSTALL_ROOT/.app-backup.XXXXXX")"
    rmdir "$BACKUP_DIR"
    mv "$APP_DIR" "$BACKUP_DIR"
fi

if ! mv "$STAGING_DIR/app" "$APP_DIR"; then
    if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
        mv "$BACKUP_DIR" "$APP_DIR" || true
    fi
    fail "impossibile attivare la nuova applicazione installata"
fi

if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
    rm -rf "$BACKUP_DIR"
fi

if [ ! -L "$LAUNCHER" ]; then
    LAUNCHER_TMP="$(mktemp "$BIN_DIR/.lele-manager-launcher.XXXXXX")"
    rm -f "$LAUNCHER_TMP"
    ln -s "$APP_EXECUTABLE" "$LAUNCHER_TMP"
    mv "$LAUNCHER_TMP" "$LAUNCHER"
fi

printf 'LeLe Manager installato in: %s\n' "$APP_DIR"
printf 'Launcher stabile: %s\n' "$LAUNCHER"
printf 'Aggiungi %s al PATH se necessario, poi esegui: lele-manager\n' "$BIN_DIR"
