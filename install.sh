#!/usr/bin/env bash
#
	# install.sh — installs this icon theme into ~/.local/share/icons
	#
	# Usage:
	#   ./install.sh [OPTIONS]
	#
	# Options:
	#   -c, COLOR   	Use a colored places variant:
	#                       b, blue     g, green    o, orange
	#                       p, pink     pu, purple  r, red
	#                       s, slate    t, teal     y, yellow
	#   -n, NAME    Install into ~/.local/share/icons/NAME
	#   -f,       	Run the custom folder icons generator after install
	#   -h,         Show this help message
	#
	# Examples:
	#   ./install.sh
	#   ./install.sh -c p
	#   ./install.sh -c purple
	#   ./install.sh -c r -n MyIcons
	#   ./install.sh -c t -f

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
MAKE_DIR="$SCRIPT_DIR/make"
COLORS_DIR="$MAKE_DIR/places-generator/colors"

AVAILABLE_COLORS=(blue green orange pink purple red slate teal yellow)

COLOR=""
THEME_NAME=""
RUN_CUSTOM_FOLDER_ICONS=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
usage() {
    sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
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

while getopts ":c:n:fh" opt; do
    case "$opt" in
        c) COLOR="$OPTARG" ;;
        n) THEME_NAME="$OPTARG" ;;
        f) RUN_CUSTOM_FOLDER_ICONS=1 ;;
        h) usage 0 ;;
        \?) die "Unknown option: -$OPTARG (use -h for help)" ;;
        :) die "Option -$OPTARG requires an argument" ;;
    esac
done

[[ -d "$SRC_DIR" ]] || die "Source directory not found: $SRC_DIR"

RESOLVED_COLOR=""
if [[ -n "$COLOR" ]]; then
    RESOLVED_COLOR="$(resolve_color "$COLOR")"
    [[ -d "$COLORS_DIR/$RESOLVED_COLOR" ]] \
        || die "Color directory not found: $COLORS_DIR/$RESOLVED_COLOR"
fi

CUSTOM_FOLDER_ICONS_SCRIPT="$MAKE_DIR/places-generator/custom_folder_icons.sh"
if [[ "$RUN_CUSTOM_FOLDER_ICONS" -eq 1 && ! -f "$CUSTOM_FOLDER_ICONS_SCRIPT" ]]; then
    die "custom_folder_icons.sh not found: $CUSTOM_FOLDER_ICONS_SCRIPT"
fi

DEST_BASE="$HOME/.local/share/icons"
if [[ -n "$THEME_NAME" ]]; then
    DEST_BASE="$DEST_BASE/$THEME_NAME"
fi

mkdir -p "$DEST_BASE"
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

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    log "Updating icon cache"
    gtk-update-icon-cache -f -t "$DEST_BASE" >/dev/null 2>&1 || true
fi

log "Done."

if [[ "$RUN_CUSTOM_FOLDER_ICONS" -eq 1 ]]; then
    log "Running custom_folder_icons.sh"
    chmod +x "$CUSTOM_FOLDER_ICONS_SCRIPT" 2>/dev/null || true
    "$CUSTOM_FOLDER_ICONS_SCRIPT"
fi
