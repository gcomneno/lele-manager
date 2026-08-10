#!/usr/bin/env bash
# Install the extracted Linux native release into stable user-local paths.

set -euo pipefail

APP_NAME="LeLe-Manager"
PRODUCT_NAME="lele-manager"
ICON_NAME="lele-manager.svg"

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
    local ancestor="$path"

    while [ "$ancestor" != "/" ]; do
        if [ -L "$ancestor" ]; then
            fail "$label non deve attraversare link simbolici: $ancestor"
        fi
        ancestor="${ancestor%/*}"
        [ -n "$ancestor" ] || ancestor="/"
    done

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

desktop_escape_argument() {
    local value="$1"

    case "$value" in
        *$'\n'*|*$'\r'*) fail "il percorso del launcher non puo' contenere newline" ;;
    esac

    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//\`/\\\`}"
    value="${value//\$/\\\$}"
    printf '"%s"' "$value"
}

desktop_file_is_owned() {
    local path="$1"
    local launcher="$2"

    [ ! -L "$path" ] || return 1
    [ -f "$path" ] || return 1
    grep -Fqx 'X-LeLe-Manager-Installer=true' "$path" && return 0

    # Adopt the narrowly recognizable pre-#178 manual workaround only.
    grep -Fqx '[Desktop Entry]' "$path" &&
        grep -Fqx 'Type=Application' "$path" &&
        grep -Fqx 'Name=LeLe Manager' "$path" &&
        grep -Fqx "Exec=$launcher" "$path" &&
        grep -Fqx "TryExec=$launcher" "$path" &&
        grep -Fqx 'Icon=lele-manager' "$path" &&
        grep -Fqx 'Terminal=false' "$path" &&
        grep -Fqx 'Categories=Development;' "$path" &&
        grep -Fqx 'StartupNotify=true' "$path"
}

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_BUNDLE="$SCRIPT_DIR/$APP_NAME"
SOURCE_EXECUTABLE="$SOURCE_BUNDLE/$APP_NAME"
SOURCE_ICON="$SCRIPT_DIR/$ICON_NAME"

[ -d "$SOURCE_BUNDLE" ] || fail "bundle nativo assente: $SOURCE_BUNDLE"
[ -f "$SOURCE_EXECUTABLE" ] || fail "eseguibile nativo assente: $SOURCE_EXECUTABLE"
[ -x "$SOURCE_EXECUTABLE" ] || fail "eseguibile nativo non eseguibile: $SOURCE_EXECUTABLE"
[ -f "$SOURCE_ICON" ] || fail "icona Linux assente: $SOURCE_ICON"

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
APPLICATIONS_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
DESKTOP_ENTRY="$APPLICATIONS_DIR/$PRODUCT_NAME.desktop"
INSTALLED_ICON="$ICON_DIR/$ICON_NAME"

require_safe_directory "$DATA_HOME" "la directory dati XDG"
require_safe_directory "$PRODUCT_ROOT" "la radice del prodotto"
require_safe_directory "$INSTALL_ROOT" "la radice di installazione"
require_safe_directory "$BIN_DIR" "la directory bin di installazione"
require_safe_directory "$APPLICATIONS_DIR" "la directory delle applicazioni XDG"
require_safe_directory "$DATA_HOME/icons" "la directory icone XDG"
require_safe_directory "$DATA_HOME/icons/hicolor" "il tema icone hicolor"
require_safe_directory "$DATA_HOME/icons/hicolor/scalable" "la directory icone scalabili"
require_safe_directory "$ICON_DIR" "la directory icone delle applicazioni"

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

if [ -L "$DESKTOP_ENTRY" ]; then
    fail "la voce desktop installata non deve essere un link simbolico: $DESKTOP_ENTRY"
fi
if [ -e "$DESKTOP_ENTRY" ] && ! desktop_file_is_owned "$DESKTOP_ENTRY" "$LAUNCHER"; then
    fail "la voce desktop esistente non appartiene a LeLe Manager: $DESKTOP_ENTRY"
fi
if [ -L "$INSTALLED_ICON" ]; then
    fail "l'icona installata non deve essere un link simbolico: $INSTALLED_ICON"
fi
if [ -e "$INSTALLED_ICON" ] && [ ! -f "$INSTALLED_ICON" ]; then
    fail "l'icona installata non e' un file regolare: $INSTALLED_ICON"
fi

STAGING_DIR="$(mktemp -d "$INSTALL_ROOT/.app-staging.XXXXXX")"
BACKUP_DIR=""
ICON_TMP="$(mktemp "$ICON_DIR/.lele-manager-icon.XXXXXX")"
DESKTOP_TMP="$(mktemp "$APPLICATIONS_DIR/.lele-manager-desktop.XXXXXX")"
cleanup() {
    local status=$?
    if [ -n "${STAGING_DIR:-}" ] && [ -d "$STAGING_DIR" ]; then
        rm -rf "$STAGING_DIR"
    fi
    [ -z "${ICON_TMP:-}" ] || rm -f "$ICON_TMP"
    [ -z "${DESKTOP_TMP:-}" ] || rm -f "$DESKTOP_TMP"
    exit "$status"
}
trap cleanup EXIT

cp -a "$SOURCE_BUNDLE" "$STAGING_DIR/app"
STAGED_EXECUTABLE="$STAGING_DIR/app/$APP_NAME"
[ -f "$STAGED_EXECUTABLE" ] || fail "copia staged senza eseguibile nativo"
[ -x "$STAGED_EXECUTABLE" ] || fail "copia staged senza eseguibile nativo eseguibile"

cp "$SOURCE_ICON" "$ICON_TMP"
[ -s "$ICON_TMP" ] || fail "copia staged senza icona Linux"
LAUNCHER_EXEC="$(desktop_escape_argument "$LAUNCHER")"
cat > "$DESKTOP_TMP" <<EOF
[Desktop Entry]
Type=Application
Name=LeLe Manager
Exec=$LAUNCHER_EXEC
TryExec=$LAUNCHER_EXEC
Icon=lele-manager
Terminal=false
Categories=Development;
StartupNotify=true
X-LeLe-Manager-Installer=true
EOF

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

mv "$ICON_TMP" "$INSTALLED_ICON"
ICON_TMP=""
mv "$DESKTOP_TMP" "$DESKTOP_ENTRY"
DESKTOP_TMP=""

printf 'LeLe Manager installato in: %s\n' "$APP_DIR"
printf 'Launcher stabile: %s\n' "$LAUNCHER"
printf 'Voce menu applicazioni: %s\n' "$DESKTOP_ENTRY"
printf 'Icona applicazione: %s\n' "$INSTALLED_ICON"
printf 'Aggiungi %s al PATH se necessario, poi esegui: lele-manager\n' "$BIN_DIR"
