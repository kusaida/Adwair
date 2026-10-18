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
# Symlinks are taken from ./links (same layout as src) and copied into the
# theme; broken symlinks are removed afterwards. The dark theme only gets
# links/apps/scalable.
#
# Dark app icons are installed as a separate theme (NAME-dark) that
# inherits the base theme.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
LINKS_DIR="$SCRIPT_DIR/links"
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
    spinner_stop
    echo "Error: $*" >&2
    exit 1
}

SPINNER_PID=""
WARNINGS=()
DONE_MSG=""

# Warnings raised while the spinner is running are queued and printed
# once it stops, so they never garble the animation line.
warn() {
    if [[ -n "$SPINNER_PID" ]]; then
        WARNINGS+=("$*")
    else
        echo "Warning: $*" >&2
    fi
}

spinner_start() {
    local msg="$1"

    if [[ ! -t 1 ]]; then
        echo "==> $msg..."
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
    local w
    if [[ -n "$SPINNER_PID" ]]; then
        kill "$SPINNER_PID" 2>/dev/null || true
        wait "$SPINNER_PID" 2>/dev/null || true
        SPINNER_PID=""
        printf '\r\033[K\033[?25h'
    fi
    for w in ${WARNINGS[@]+"${WARNINGS[@]}"}; do
        echo "Warning: $w" >&2
    done
    WARNINGS=()
}

finish() {
    [[ -z "$DONE_MSG" ]] || echo "==> $DONE_MSG"
}

prune_broken_links() {
    find "$1" -xtype l -delete
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
        --)             shift; ARGS+=(-- "$@"); break ;;
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
shift $((OPTIND - 1))
[[ $# -eq 0 ]] || die "Unexpected argument: $1 (options must come before it; use -h for help)"

case "$INSTALL_PATH" in
    "~")   INSTALL_PATH="$HOME" ;;
    "~/"*) INSTALL_PATH="$HOME/${INSTALL_PATH#"~/"}" ;;
esac
INSTALL_PATH="${INSTALL_PATH%/}"
[[ -n "$INSTALL_PATH" ]] || die "Installation path must not be empty or '/'"

[[ -n "$THEME_NAME" && "$THEME_NAME" != */* && "$THEME_NAME" != "." && "$THEME_NAME" != ".." ]] \
    || die "Invalid theme name '$THEME_NAME' (must be non-empty, without '/', not '.' or '..')"

DEST_BASE="$INSTALL_PATH/$THEME_NAME"
DARK_THEME_NAME="${THEME_NAME}-dark"
DARK_BASE="$INSTALL_PATH/$DARK_THEME_NAME"

uninstall() {
    local dir

    if [[ ! -d "$DEST_BASE" && ! -d "$DARK_BASE" ]]; then
        DONE_MSG="Nothing to uninstall: '$DEST_BASE' does not exist"
        return 0
    fi

    spinner_start "Uninstalling theme from $DEST_BASE"
    for dir in "$DEST_BASE" "$DARK_BASE"; do
        [[ -d "$dir" ]] || continue
        rm -rf -- "$dir" \
            || die "Cannot remove $dir (permission denied? try sudo for system paths)"
    done
    spinner_stop
    DONE_MSG="Theme uninstalled from $DEST_BASE"
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
        local -a extra_list=()
        IFS=':' read -ra extra_list <<< "$EXTRA_ROOTS"
        for extra in ${extra_list[@]+"${extra_list[@]}"}; do
            fi_add_root "$extra"
        done
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
    local line cur="" val
    local -A handled=()

    build_protected_folders
    build_folder_roots

    spinner_start "Resetting folder icons"

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
                    continue
                fi
                "${GIO_CMD[@]}" set "$cur" metadata::custom-icon-name -d 2>/dev/null \
                    || warn "failed to reset $cur"
                ;;
        esac
    done < <(find "${FI_ROOTS[@]}" -xdev -type d -print0 2>/dev/null \
                 | xargs -0 -r -n 200 "${GIO_CMD[@]}" info -a metadata::custom-icon-name 2>/dev/null || true)

    spinner_stop
}

assign_folder_icons() {
    local catalog="${FI_CATALOG:-}" icon_file base keyword t dir name lname best bestlen
    local nname nt
    local -A term_icon=() handled=()
    local -a find_names=()

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
        warn "no non-standard folder-*.svg icons in $catalog — nothing to assign."
        return 0
    fi

    build_protected_folders
    build_folder_roots

    for t in "${!term_icon[@]}"; do find_names+=(-o -iname "*${t}*"); done
    find_names=("${find_names[@]:1}")

    spinner_start "Assigning folder icons"

    while IFS= read -r -d '' dir; do
        [[ -z "${handled[$dir]:-}" ]] || continue
        handled["$dir"]=1

        if is_protected_folder "$dir"; then
            continue
        fi

        # Match whole words only: separators (- _ .) count as spaces, so
        # "my-work" / "Work_2024" match "work", but "network" does not.
        name="${dir##*/}"; lname="${name,,}"; best=""; bestlen=0
        nname=" ${lname//[-_.]/ } "
        for t in "${!term_icon[@]}"; do
            nt="${t//[-_.]/ }"
            if [[ "$nname" == *" $nt "* && "${#t}" -gt "$bestlen" ]]; then
                best="${term_icon[$t]}"; bestlen="${#t}"
            fi
        done
        [[ -n "$best" ]] || continue

        "${GIO_CMD[@]}" set "$dir" metadata::custom-icon-name "$best" 2>/dev/null \
            || warn "failed to set icon for $dir"
    done < <(find "${FI_ROOTS[@]}" -xdev \
                  \( -path "$SCRIPT_DIR" -o -path "$DEST_BASE" -o -name '.?*' -o -name node_modules \) -prune -o \
                  -type d \( "${find_names[@]}" \) -print0 2>/dev/null || true)

    spinner_stop
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
    finish
    exit 0
fi

[[ -d "$SRC_DIR" ]] || die "Source directory not found: $SRC_DIR"
[[ -d "$LINKS_DIR" ]] || die "Links directory not found: $LINKS_DIR"
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

spinner_start "Installing theme to $DEST_BASE"

mkdir -p "$DEST_BASE" 2>/dev/null \
    || die "Cannot create $DEST_BASE (permission denied? try sudo for system paths)"

for dir in "$SRC_DIR"/*/; do
    name="$(basename "$dir")"
    mkdir -p "$DEST_BASE/$name"
    cp -a --remove-destination "$dir." "$DEST_BASE/$name/"
done

cp -a --remove-destination "$LINKS_DIR/." "$DEST_BASE/"

INDEX_THEME=""
if [[ -f "$SCRIPT_DIR/index.theme" ]]; then
    INDEX_THEME="$SCRIPT_DIR/index.theme"
elif [[ -f "$SRC_DIR/index.theme" ]]; then
    INDEX_THEME="$SRC_DIR/index.theme"
fi

if [[ -n "$INDEX_THEME" ]]; then
    cp -f "$INDEX_THEME" "$DEST_BASE/"
else
    warn "index.theme not found next to $SCRIPT_DIR or in $SRC_DIR — skipping."
fi

if [[ -n "$RESOLVED_COLOR" ]]; then
    COLOR_SRC_DIR="$COLORS_DIR/$RESOLVED_COLOR"
    PLACES_DEST="$DEST_BASE/places/scalable"

    mkdir -p "$PLACES_DEST"

    shopt -s nullglob
    files=("$COLOR_SRC_DIR"/*)
    shopt -u nullglob

    if [[ ${#files[@]} -eq 0 ]]; then
        die "No files found in $COLOR_SRC_DIR"
    fi

    for f in "${files[@]}"; do
        cp -f --remove-destination "$f" "$PLACES_DEST/"
    done
fi

if [[ "$INSTALL_APPS" -eq 1 ]]; then
    APPS_SRC="$APPS_COLORS_DIR/$RESOLVED_COLOR"
    APPS_DEST="$DEST_BASE/apps/scalable"

    mkdir -p "$APPS_DEST"

    shopt -s nullglob
    app_files=("$APPS_SRC"/*)
    shopt -u nullglob

    [[ ${#app_files[@]} -gt 0 ]] || die "No files found in $APPS_SRC"

    for f in "${app_files[@]}"; do
        cp -f --remove-destination "$f" "$APPS_DEST/"
    done
fi

mkdir -p "$DARK_BASE/apps/scalable" 2>/dev/null \
    || die "Cannot create $DARK_BASE (permission denied? try sudo for system paths)"

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

DARK_APPS="$DARK_BASE/apps/scalable"

if [[ -d "$LINKS_DIR/apps/scalable" ]]; then
    cp -a --remove-destination "$LINKS_DIR/apps/scalable/." "$DARK_APPS/"
else
    warn "$LINKS_DIR/apps/scalable not found — no alias symlinks for dark theme."
fi

dark_files=()
while IFS= read -r -d '' f; do
    dark_files+=("$f")
done < <(find "$DARK_DIR" -maxdepth 1 \( -type f -o -type l \) \
              \( -name '*.svg' -o -name '*.svgz' \) -print0)

dark_count=${#dark_files[@]}
[[ "$dark_count" -gt 0 ]] || die "No icons found in $DARK_DIR"
cp -a --remove-destination -t "$DARK_APPS/" "${dark_files[@]}"

prune_broken_links "$DARK_BASE"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$DEST_BASE" >/dev/null 2>&1 &
    pid_base=$!
    gtk-update-icon-cache -f -t "$DARK_BASE" >/dev/null 2>&1 &
    pid_dark=$!
    wait "$pid_base" 2>/dev/null || true
    wait "$pid_dark" 2>/dev/null || true
fi

spinner_stop
DONE_MSG="Theme installed to $DEST_BASE"

if [[ "$RUN_FOLDER_ICONS" -eq 1 ]]; then
    assign_folder_icons
fi

finish
