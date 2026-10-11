#!/usr/bin/env bash
#
# install.sh — installs this icon theme into ~/.local/share/icons
#
# Usage:
#   ./install.sh [OPTIONS]
#
# Options:
#   -c, --color [COLOR]  Use a colored places variant. (default: blue).
#                        or an unambiguous prefix, case-insensitive:
#                          b, blue     g, green    o, orange
#                          p, pink     pu, purple  r, red
#                          s, slate    t, teal     y, yellow
#   -a, --apps           Also install colored app icons. Requires -c. (default: blue).
#   -n, --name NAME      Theme folder name (default: Adwair)
#   -p, --path PATH      Base installation path (default: ~/.local/share/icons)
#                        The theme is installed into PATH/NAME
#   -f, --folder-icons   After install, assign folder icons BY NAME.
#                        Requires gio. Cannot be combined with -r.
#   -r, --remove,
#   -u, --uninstall      Uninstall (remove) the theme PATH/NAME and its
#                        dark variant PATH/NAME-dark.
#                        Respects -p and -n;
#   -F, --folder-name    Only with -r/-u: after removing the theme, also reset
#                        the folder icons set by -f.
#   -h, --help           Show this help message
#
# Dark app icons are installed as a separate theme (NAME-dark) that
# inherits the base theme.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
MAKE_DIR="$SCRIPT_DIR/make"
COLORS_DIR="$MAKE_DIR/generator/colors"
APPS_COLORS_DIR="$MAKE_DIR/generator/apps"
DARK_DIR="$MAKE_DIR/generator/dark"

AVAILABLE_COLORS=(blue green orange pink purple red slate teal yellow)

COLOR=""
COLOR_SET=0
THEME_NAME="Adwair"
INSTALL_PATH="$HOME/.local/share/icons"
RUN_FOLDER_ICONS=0
INSTALL_APPS=0
REMOVE=0
RESET_FOLDERS=0
INCLUDE_MOUNTS="${INCLUDE_MOUNTS:-1}"
EXTRA_ROOTS="${EXTRA_ROOTS:-}"
SEARCH_ROOT="${SEARCH_ROOT:-}"

STANDARD_ICONS=(
    folder folder-documents folder-download folder-drag-accept folder-music
    folder-pictures folder-publicshare folder-remote folder-templates folder-videos
    network-server network-workgroup user-bookmarks user-desktop user-home user-trash
)

declare -A TRANSLATIONS=(
    [games]="игры"
    [photos]="фото"
    [projects]="проекты"
    [work]="работа"
    [study]="учеба"
    [books]="книги"
    [archive]="архив"
    [backup]="резервная копия"
    [notes]="заметки"
)

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
        --color|-c|-[afruF]*c)
            if [[ "$1" =~ ^-[afruF]+c$ ]]; then
                ARGS+=("${1%c}")
            elif [[ "$1" != "-c" && "$1" != "--color" ]]; then
                ARGS+=("$1"); shift; continue
            fi
            if [[ $# -ge 2 && "$2" != -* ]]; then
                ARGS+=(-c "$2")
                shift
            else
                ARGS+=(-c "")
            fi
            ;;
        --name|--path)
            [[ $# -ge 2 ]] || die "Option $1 requires an argument"
            ARGS+=("-${1:2:1}" "$2")
            shift
            ;;
        --folder-icons) ARGS+=(-f) ;;
        --apps)         ARGS+=(-a) ;;
        --remove)       ARGS+=(-r) ;;
        --uninstall)    ARGS+=(-u) ;;
        --folder-name)  ARGS+=(-F) ;;
        --help)         ARGS+=(-h) ;;
        --)             shift; ARGS+=("$@"); break ;;
        --*)            die "Unknown option: $1 (use -h for help)" ;;
        *)              ARGS+=("$1") ;;
    esac
    shift
done
set -- ${ARGS[@]+"${ARGS[@]}"}

while getopts ":c:n:p:afruFh" opt; do
    case "$opt" in
        c) COLOR="$OPTARG"; COLOR_SET=1 ;;
        n) THEME_NAME="$OPTARG" ;;
        p) INSTALL_PATH="$OPTARG" ;;
        a) INSTALL_APPS=1 ;;
        f) RUN_FOLDER_ICONS=1 ;;
        r|u) REMOVE=1 ;;
        F) RESET_FOLDERS=1 ;;
        h) usage 0 ;;
        \?) die "Unknown option: -$OPTARG (use -h for help)" ;;
        :) die "Option -$OPTARG requires an argument" ;;
    esac
done

case "$INSTALL_PATH" in
    "~")   INSTALL_PATH="$HOME" ;;
    "~/"*) INSTALL_PATH="$HOME/${INSTALL_PATH#"~/"}" ;;
esac
INSTALL_PATH="${INSTALL_PATH%/}"
[[ -n "$INSTALL_PATH" ]] || die "Installation path must not be empty or '/'"

DEST_BASE="$INSTALL_PATH/$THEME_NAME"
DARK_THEME_NAME="${THEME_NAME}-dark"
DARK_BASE="$INSTALL_PATH/$DARK_THEME_NAME"

uninstall() {
    [[ -n "$THEME_NAME" && "$THEME_NAME" != *"/"* && "$THEME_NAME" != "." && "$THEME_NAME" != ".." ]] \
        || die "Invalid theme name '$THEME_NAME'"

    local dir found=0
    for dir in "$DEST_BASE" "$DARK_BASE"; do
        [[ -d "$dir" ]] || continue
        found=1
        log "Uninstalling '$dir'..."
        rm -rf -- "$dir" \
            || die "Cannot remove $dir (permission denied? try sudo for system paths)"
    done
    if [[ "$found" -eq 1 ]]; then
        log "Done."
    else
        log "Nothing to uninstall: '$DEST_BASE' does not exist"
    fi
}

FI_ROOTS=()
FI_PROTECTED=()
TARGET_HOME="$HOME"
GIO_CMD=(env LC_ALL=C gio)

setup_folder_tools() {
    command -v gio >/dev/null 2>&1 || die "gio not found (required by -f / -F)"

    if [[ "$EUID" -eq 0 && -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
        TARGET_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
        [[ -n "$TARGET_HOME" ]] || die "Cannot determine home directory of $SUDO_USER"
        GIO_CMD=(sudo -u "$SUDO_USER" env LC_ALL=C
                 "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u "$SUDO_USER")/bus" gio)
    fi
}

build_protected_folders() {
    local cfg="$TARGET_HOME/.config/user-dirs.dirs" line path n
    local re='^XDG_[A-Z]+_DIR="(.*)"$'

    if [[ -r "$cfg" ]]; then
        while IFS= read -r line; do
            [[ "$line" =~ $re ]] || continue
            path="${BASH_REMATCH[1]//\$HOME/$TARGET_HOME}"
            FI_PROTECTED+=("${path%/}")
        done < "$cfg"
    fi

    for n in Desktop Documents Downloads Music Pictures Photos Videos Templates Public; do
        FI_PROTECTED+=("$TARGET_HOME/$n")
    done
    FI_PROTECTED+=("$TARGET_HOME")
}

is_standard_icon() {
    local i
    for i in "${STANDARD_ICONS[@]}"; do
        [[ "$1" == "$i" ]] && return 0
    done
    return 1
}

is_protected_folder() {
    local p
    for p in ${FI_PROTECTED[@]+"${FI_PROTECTED[@]}"}; do
        [[ "$1" == "$p" ]] && return 0
    done
    return 1
}

fi_add_root() {
    local c="${1%/}" r
    [[ -d "$c" ]] || return 0
    for r in ${FI_ROOTS[@]+"${FI_ROOTS[@]}"}; do
        [[ "$c" == "$r" || "$c" == "$r"/* ]] && return 0
    done
    FI_ROOTS+=("$c")
}

build_folder_roots() {
    local extra target fstype
    local excl='^(proc|sysfs|devtmpfs|tmpfs|devpts|cgroup2?|pstore|bpf|configfs|fusectl|binfmt_misc|autofs|mqueue|hugetlbfs|debugfs|tracefs|securityfs|ramfs|squashfs|overlay|nsfs|efivarfs|rpc_pipefs)$'

    fi_add_root "${SEARCH_ROOT:-$TARGET_HOME}"

    if [[ -n "$EXTRA_ROOTS" ]]; then
        local IFS=':'
        for extra in $EXTRA_ROOTS; do fi_add_root "$extra"; done
    fi

    if [[ "$INCLUDE_MOUNTS" -eq 1 ]]; then
        while read -r target fstype; do
            [[ "$fstype" =~ $excl ]] && continue
            target="$(printf '%b' "$target")"
            case "$target" in
                / | /boot | /boot/* | /dev | /dev/* | /proc | /proc/* | /sys | /sys/* | /run | /run/* ) continue ;;
            esac
            fi_add_root "$target"
        done < <(findmnt -rn -o TARGET,FSTYPE 2>/dev/null || awk '{print $2, $3}' /proc/mounts 2>/dev/null || true)
    fi
}

reset_folder_icons() {
    local line cur="" val r reset=0 skipped=0 failed=0
    local -A handled=()

    build_protected_folders
    build_folder_roots

    log "Resetting folder icon metadata (folder-* only)"
    for r in "${FI_ROOTS[@]}"; do log "  scanning $r"; done

    while IFS= read -r line; do
        case "$line" in
            "local path: "*)
                cur="${line#local path: }"
                ;;
            *"metadata::custom-icon-name: "*)
                val="${line#*metadata::custom-icon-name: }"
                [[ -n "$cur" && "$val" == folder-* ]] || continue
                [[ -z "${handled[$cur]:-}" ]] || continue
                handled["$cur"]=1

                if is_protected_folder "$cur" || is_standard_icon "$val"; then
                    log "  skipped standard: $cur ($val)"
                    skipped=$((skipped + 1))
                elif "${GIO_CMD[@]}" set "$cur" metadata::custom-icon-name -d 2>/dev/null; then
                    log "  reset: $cur ($val)"
                    reset=$((reset + 1))
                else
                    echo "Warning: failed to reset $cur" >&2
                    failed=$((failed + 1))
                fi
                ;;
        esac
    done < <(find "${FI_ROOTS[@]}" -xdev -type d -print0 2>/dev/null \
                 | xargs -0 -r -n 200 "${GIO_CMD[@]}" info -a metadata::custom-icon-name 2>/dev/null || true)

    log "Folder icons: $reset reset, $skipped standard skipped, $failed failed"
}

SPINNER_PID=""

spinner_start() {
    local msg="$1"

    if [[ ! -t 1 ]]; then
        log "$msg..."
        return 0
    fi

    (
        local frames=('|' '/' '-' '\') i=0
        case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in
            *[Uu][Tt][Ff]-8*|*[Uu][Tt][Ff]8*) frames=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏) ;;
        esac
        while true; do
            printf '\r==> %s %s' "${frames[i % ${#frames[@]}]}" "$msg"
            i=$((i + 1))
            sleep 0.1
        done
    ) &
    SPINNER_PID=$!
    printf '\033[?25l'
    trap 'spinner_stop' EXIT
    trap 'spinner_stop; exit 130' INT TERM
}

spinner_stop() {
    [[ -n "$SPINNER_PID" ]] || return 0
    kill "$SPINNER_PID" 2>/dev/null || true
    wait "$SPINNER_PID" 2>/dev/null || true
    SPINNER_PID=""
    printf '\r\033[K\033[?25h'
}

assign_folder_icons() {
    local catalog="${FI_CATALOG:-}" icon_file base keyword t dir name lname best bestlen
    local assigned=0 skipped=0 failed=0
    local -A term_icon=() handled=()
    local -a find_names=() fail_list=()

    [[ -n "$catalog" && -d "$catalog" ]] || catalog="$DEST_BASE/places/scalable"
    [[ -d "$catalog" ]] || die "Folder icon catalog not found: $catalog"

    case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in
        ""|C|POSIX) export LC_ALL=C.UTF-8 ;;
    esac

    shopt -s nullglob
    for icon_file in "$catalog"/folder-*.svg; do
        base="$(basename "$icon_file" .svg)"
        keyword="${base#folder-}"
        [[ -n "$keyword" ]] || continue
        is_standard_icon "$base" && continue
        term_icon["${keyword,,}"]="$base"
        [[ -z "${TRANSLATIONS[$keyword]:-}" ]] || term_icon["${TRANSLATIONS[$keyword],,}"]="$base"
    done
    shopt -u nullglob

    if [[ "${#term_icon[@]}" -eq 0 ]]; then
        echo "Warning: no non-standard folder-*.svg icons in $catalog — nothing to assign." >&2
        return 0
    fi

    build_protected_folders
    build_folder_roots

    for t in "${!term_icon[@]}"; do find_names+=(-o -iname "*${t}*"); done
    find_names=("${find_names[@]:1}")

    spinner_start "Matching icons"

    while IFS= read -r -d '' dir; do
        [[ -z "${handled[$dir]:-}" ]] || continue
        handled["$dir"]=1

        if is_protected_folder "$dir"; then
            skipped=$((skipped + 1))
            continue
        fi

        name="${dir##*/}"; lname="${name,,}"; best=""; bestlen=0
        for t in "${!term_icon[@]}"; do
            if [[ "$lname" == *"$t"* && "${#t}" -gt "$bestlen" ]]; then
                best="${term_icon[$t]}"; bestlen="${#t}"
            fi
        done
        [[ -n "$best" ]] || continue

        if "${GIO_CMD[@]}" set "$dir" metadata::custom-icon-name "$best" 2>/dev/null; then
            assigned=$((assigned + 1))
        else
            fail_list+=("$dir")
            failed=$((failed + 1))
        fi
    done < <(find "${FI_ROOTS[@]}" -xdev \( -path "$SCRIPT_DIR" -o -path "$DEST_BASE" \) -prune -o \
                  -type d \( "${find_names[@]}" \) -print0 2>/dev/null || true)

    spinner_stop

    for dir in ${fail_list[@]+"${fail_list[@]}"}; do
        echo "Warning: failed to set icon for $dir" >&2
    done
    log "Folder icons: $assigned assigned, $skipped standard skipped, $failed failed"
}

if [[ "$RESET_FOLDERS" -eq 1 && "$REMOVE" -ne 1 ]]; then
    die "Option -F/--folder-name can only be used with -r/--uninstall"
fi
if [[ "$RUN_FOLDER_ICONS" -eq 1 && "$REMOVE" -eq 1 ]]; then
    die "Option -f/--folder-icons cannot be used with -r/--uninstall"
fi
[[ "$RESET_FOLDERS" -eq 0 && "$RUN_FOLDER_ICONS" -eq 0 ]] || setup_folder_tools

if [[ "$REMOVE" -eq 1 ]]; then
    uninstall
    [[ "$RESET_FOLDERS" -eq 0 ]] || reset_folder_icons
    exit 0
fi

[[ -d "$SRC_DIR" ]] || die "Source directory not found: $SRC_DIR"
[[ -d "$DARK_DIR" ]] || die "Dark icons directory not found: $DARK_DIR"

RESOLVED_COLOR="$(resolve_color "${COLOR:-blue}")"
[[ -d "$COLORS_DIR/$RESOLVED_COLOR" ]] \
    || die "Color directory not found: $COLORS_DIR/$RESOLVED_COLOR"

if [[ "$INSTALL_APPS" -eq 1 ]]; then
    [[ "$COLOR_SET" -eq 1 ]] || die "Option -a requires -c (COLOR may be omitted: -c -a = blue)"
    [[ -d "$APPS_COLORS_DIR/$RESOLVED_COLOR" ]] \
        || die "App color directory not found: $APPS_COLORS_DIR/$RESOLVED_COLOR (run generate_icons.py first)"
fi

FI_CATALOG=""
if [[ "$RUN_FOLDER_ICONS" -eq 1 ]]; then
    FI_CATALOG="$COLORS_DIR/$RESOLVED_COLOR"
fi

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

# Copy dark icons in a single cp call instead of one cp per file.
dark_files=()
while IFS= read -r -d '' f; do
    dark_files+=("$f")
done < <(find "$DARK_DIR" -maxdepth 1 \( -type f -o -type l \) \
              \( -name '*.svg' -o -name '*.svgz' \) -print0)

dark_count=${#dark_files[@]}
[[ "$dark_count" -gt 0 ]] || die "No icons found in $DARK_DIR"
cp -at "$DARK_BASE/apps/scalable/" "${dark_files[@]}"
log "  copied $dark_count file(s) to $DARK_BASE/apps/scalable"

# Symlinked icon names in the base theme must exist in the dark theme too,
# otherwise lookups for them fall back to the base theme via Inherits and
# return light artwork. Link them to the dark variant of their target.
#
# Performance: one find collects all base symlinks (name -> direct target);
# chains (alias -> alias -> file) are resolved in pure bash, so no
# basename/readlink forks per icon.
DARK_APPS="$DARK_BASE/apps/scalable"
declare -A base_links=()
while IFS=$'\t' read -r alias_name target; do
    base_links["$alias_name"]="$target"
done < <(find "$DEST_BASE/apps/scalable" -maxdepth 1 -type l -printf '%f\t%l\n')

alias_count=0
for alias_name in "${!base_links[@]}"; do
    [[ -e "$DARK_APPS/$alias_name" || -L "$DARK_APPS/$alias_name" ]] && continue

    # Resolve the chain down to the final file name (like readlink -f + basename).
    target_name="${base_links[$alias_name]##*/}"
    hops=0
    while [[ -n "${base_links[$target_name]:-}" && "$hops" -lt 40 ]]; do
        target_name="${base_links[$target_name]##*/}"
        hops=$((hops + 1))
    done
    [[ -n "$target_name" ]] || continue

    if [[ -e "$DARK_APPS/$target_name" || -L "$DARK_APPS/$target_name" ]]; then
        ln -sfn "$target_name" "$DARK_APPS/$alias_name"
        alias_count=$((alias_count + 1))
    fi
done
unset base_links
log "  linked $alias_count alias icon(s) to dark variants"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    log "Updating icon cache"
    gtk-update-icon-cache -f -t "$DEST_BASE" >/dev/null 2>&1 &
    pid_base=$!
    gtk-update-icon-cache -f -t "$DARK_BASE" >/dev/null 2>&1 &
    pid_dark=$!
    wait "$pid_base" 2>/dev/null || true
    wait "$pid_dark" 2>/dev/null || true
fi

log "Done."

if [[ "$RUN_FOLDER_ICONS" -eq 1 ]]; then
    assign_folder_icons
fi
