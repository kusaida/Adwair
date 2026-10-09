#!/usr/bin/env bash
#
# install.sh — installs this icon theme into ~/.local/share/icons
#
# Usage:
#   ./install.sh [OPTIONS]
#
# Options:
#   -c, --color COLOR    Use a colored places variant (default: blue).
#                        Accepts the full name or an unambiguous prefix,
#                        case-insensitive:
#                          b, blue     g, green    o, orange
#                          p, pink     pu, purple  r, red
#                          s, slate    t, teal     y, yellow
#   -a, --apps           Also install colored app icons into apps/scalable,
#                        using the color from -c (default: blue).
#                        Currently only provides a recolored file-manager icon
#   -n, --name NAME      Theme folder name (default: Adwair)
#                        The dark variant is installed as NAME-dark
#   -p, --path PATH      Base installation path (default: ~/.local/share/icons)
#                        The theme is installed into PATH/NAME
#   -f, --folder-icons   Run the custom folder icons generator after install
#   -h, --help           Show this help message
#
# Dark app icons are installed as a separate theme (Adwair-dark by default)
# that inherits the base theme.
#
#
# Examples:
#   ./install.sh
#   ./install.sh -c p
#   ./install.sh --color purple
#   ./install.sh -c r -n MyIcons
#   ./install.sh --color teal --name MyIcons --folder-icons
#   ./install.sh -c r -a
#   ./install.sh --color teal --apps
#   ./install.sh -p ~/.icons
#   sudo ./install.sh --path /usr/share/icons

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
MAKE_DIR="$SCRIPT_DIR/make"
COLORS_DIR="$MAKE_DIR/generator/colors"
APPS_COLORS_DIR="$MAKE_DIR/generator/apps"
DARK_DIR="$MAKE_DIR/generator/dark"

AVAILABLE_COLORS=(blue green orange pink purple red slate teal yellow)

COLOR="blue"
THEME_NAME="Adwair"
INSTALL_PATH="$HOME/.local/share/icons"
RUN_FOLDER_ICONS=0
INSTALL_APPS=0

usage() {
    awk 'NR==1{next} /^[[:space:]]*#/{print; next} {exit}' "$0" \
        | sed -E 's/^[[:space:]]*# ?//'
    exit "${1:-0}"
}

die() {
    echo "Error: $*" >&2
    exit 1
}

log() {
    echo "==> $*"
}

resolve_color() {
    local input="$1"
    local lower
    lower="$(echo "$input" | tr '[:upper:]' '[:lower:]')"

    for c in "${AVAILABLE_COLORS[@]}"; do
        [[ "$c" == "$lower" ]] && { echo "$c"; return 0; }
    done

    if [[ "$lower" == "p" ]]; then
        echo "pink"
        return 0
    fi

    local matches=()
    for c in "${AVAILABLE_COLORS[@]}"; do
        [[ "$c" == "$lower"* ]] && matches+=("$c")
    done

    case "${#matches[@]}" in
        1)
            echo "${matches[0]}"
            return 0
            ;;
        0)
            die "Unknown color '$input'. Available colors: ${AVAILABLE_COLORS[*]}"
            ;;
        *)
            die "Color '$input' is ambiguous (matches: ${matches[*]}). Be more specific, e.g. 'pu' for purple."
            ;;
    esac
}

ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --color=*|--name=*|--path=*)
            long="${1%%=*}"
            ARGS+=("-${long:2:1}" "${1#*=}")
            ;;
        --color|--name|--path)
            [[ $# -ge 2 ]] || die "Option $1 requires an argument"
            ARGS+=("-${1:2:1}" "$2")
            shift
            ;;
        --folder-icons) ARGS+=(-f) ;;
        --apps)         ARGS+=(-a) ;;
        --help)         ARGS+=(-h) ;;
        --)             shift; ARGS+=("$@"); break ;;
        --*)            die "Unknown option: $1 (use -h for help)" ;;
        *)              ARGS+=("$1") ;;
    esac
    shift
done
set -- ${ARGS[@]+"${ARGS[@]}"}

while getopts ":c:n:p:afh" opt; do
    case "$opt" in
        c) COLOR="$OPTARG" ;;
        n) THEME_NAME="$OPTARG" ;;
        p) INSTALL_PATH="$OPTARG" ;;
        a) INSTALL_APPS=1 ;;
        f) RUN_FOLDER_ICONS=1 ;;
        h) usage 0 ;;
        \?) die "Unknown option: -$OPTARG (use -h for help)" ;;
        :) die "Option -$OPTARG requires an argument" ;;
    esac
done

[[ -d "$SRC_DIR" ]] || die "Source directory not found: $SRC_DIR"
[[ -d "$DARK_DIR" ]] || die "Dark icons directory not found: $DARK_DIR"

RESOLVED_COLOR=""
if [[ -n "$COLOR" ]]; then
    RESOLVED_COLOR="$(resolve_color "$COLOR")"
    [[ -d "$COLORS_DIR/$RESOLVED_COLOR" ]] \
        || die "Color directory not found: $COLORS_DIR/$RESOLVED_COLOR"
fi

if [[ "$INSTALL_APPS" -eq 1 ]]; then
    [[ -n "$RESOLVED_COLOR" ]] || die "Option -a requires a color (-c)"
    [[ -d "$APPS_COLORS_DIR/$RESOLVED_COLOR" ]] \
        || die "App color directory not found: $APPS_COLORS_DIR/$RESOLVED_COLOR (run generate_icons.py first)"
fi

FOLDER_ICONS_SCRIPT="$MAKE_DIR/generator/folder_icons.sh"
if [[ "$RUN_FOLDER_ICONS" -eq 1 && ! -f "$FOLDER_ICONS_SCRIPT" ]]; then
    die "folder_icons.sh not found: $FOLDER_ICONS_SCRIPT"
fi

case "$INSTALL_PATH" in
    "~")   INSTALL_PATH="$HOME" ;;
    "~/"*) INSTALL_PATH="$HOME/${INSTALL_PATH#"~/"}" ;;
esac
INSTALL_PATH="${INSTALL_PATH%/}"
[[ -n "$INSTALL_PATH" ]] || die "Installation path must not be empty or '/'"

DEST_BASE="$INSTALL_PATH/$THEME_NAME"
DARK_THEME_NAME="${THEME_NAME}-dark"
DARK_BASE="$INSTALL_PATH/$DARK_THEME_NAME"

mkdir -p "$DEST_BASE" 2>/dev/null \
    || die "Cannot create $DEST_BASE (permission denied? try sudo for system paths)"
log "Installing icons to: $DEST_BASE"

for dir in "$SRC_DIR"/*/; do
    name="$(basename "$dir")"
    log "  copying $name/"
    mkdir -p "$DEST_BASE/$name"
    cp -a "$dir." "$DEST_BASE/$name/"
done

INDEX_THEME=""
if [[ -f "$SCRIPT_DIR/index.theme" ]]; then
    INDEX_THEME="$SCRIPT_DIR/index.theme"
elif [[ -f "$SRC_DIR/index.theme" ]]; then
    INDEX_THEME="$SRC_DIR/index.theme"
fi

if [[ -n "$INDEX_THEME" ]]; then
    log "  copying index.theme"
    cp -f "$INDEX_THEME" "$DEST_BASE/"
else
    echo "Warning: index.theme not found next to $SCRIPT_DIR or in $SRC_DIR — skipping." >&2
fi

if [[ -n "$RESOLVED_COLOR" ]]; then
    COLOR_SRC_DIR="$COLORS_DIR/$RESOLVED_COLOR"
    PLACES_DEST="$DEST_BASE/places/scalable"

    log "Applying '$RESOLVED_COLOR' color variant to places/scalable"
    mkdir -p "$PLACES_DEST"

    shopt -s nullglob
    files=("$COLOR_SRC_DIR"/*)
    shopt -u nullglob

    if [[ ${#files[@]} -eq 0 ]]; then
        die "No files found in $COLOR_SRC_DIR"
    fi

    for f in "${files[@]}"; do
        cp -f "$f" "$PLACES_DEST/"
    done
    log "  replaced $(printf '%s\n' "${files[@]}" | wc -l) file(s) in $PLACES_DEST"
fi

if [[ "$INSTALL_APPS" -eq 1 ]]; then
    APPS_SRC="$APPS_COLORS_DIR/$RESOLVED_COLOR"
    APPS_DEST="$DEST_BASE/apps/scalable"

    log "Applying '$RESOLVED_COLOR' color variant to apps/scalable"
    mkdir -p "$APPS_DEST"

    shopt -s nullglob
    app_files=("$APPS_SRC"/*)
    shopt -u nullglob

    [[ ${#app_files[@]} -gt 0 ]] || die "No files found in $APPS_SRC"

    for f in "${app_files[@]}"; do
        cp -f "$f" "$APPS_DEST/"
    done
    log "  replaced ${#app_files[@]} file(s) in $APPS_DEST"
fi

mkdir -p "$DARK_BASE/apps/scalable" 2>/dev/null \
    || die "Cannot create $DARK_BASE (permission denied? try sudo for system paths)"
log "Installing dark theme to: $DARK_BASE"

cat > "$DARK_BASE/index.theme" <<EOF
[Icon Theme]
Name=$DARK_THEME_NAME
Comment=Dark app icons for $THEME_NAME. Inherits the base theme.
Inherits=$THEME_NAME
Example=folder
FollowsColorScheme=true
KDE-Extensions=.svg

Directories=apps/scalable

[apps/scalable]
Size=64
Context=Applications
Type=Scalable
MinSize=16
MaxSize=512
EOF

dark_count=0
while IFS= read -r -d '' f; do
    cp -af "$f" "$DARK_BASE/apps/scalable/"
    dark_count=$((dark_count + 1))
done < <(find "$DARK_DIR" -maxdepth 1 \( -type f -o -type l \) \
              \( -name '*.svg' -o -name '*.svgz' \) -print0)

[[ "$dark_count" -gt 0 ]] || die "No icons found in $DARK_DIR"
log "  copied $dark_count file(s) to $DARK_BASE/apps/scalable"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    log "Updating icon cache"
    gtk-update-icon-cache -f -t "$DEST_BASE" >/dev/null 2>&1 || true
    gtk-update-icon-cache -f -t "$DARK_BASE" >/dev/null 2>&1 || true
fi

log "Done."

if [[ "$RUN_FOLDER_ICONS" -eq 1 ]]; then
    log "Running folder_icons.sh"
    chmod +x "$FOLDER_ICONS_SCRIPT" 2>/dev/null || true
    "$FOLDER_ICONS_SCRIPT"
fi
