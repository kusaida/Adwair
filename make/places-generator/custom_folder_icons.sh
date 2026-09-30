#!/usr/bin/env bash

# --------------------------------------------------------------------------------------------------
#
# Automate change of folder icons using gio, driven entirely by the icon files themselves.
#
# - The <script_dir>/colors/<COLOR> (default: blue) directory next to this script is used ONLY as a
#   CATALOG to discover which icon names exist (by listing folder-*.svg filenames there) and to know
#   which keyword to search folder names for. It is NOT the source of what gets assigned.
# - Folders are assigned the ICON NAME ONLY (e.g. "folder-projects"), via
#   metadata::custom-icon-name, never a file:// path to a specific SVG. GNOME/Nautilus then resolves
#   that name against whichever icon theme is currently active, in whatever color/variant it ships.
#   This means the actual rendered icon always follows the active theme -- swap themes and the
#   folders update automatically, with no path pointing at a specific SVG anywhere.
# - For every icon name "folder-<word>" found in the catalog, it recursively searches every SEARCH
#   ROOT for folders whose NAME CONTAINS <word> (case-insensitive substring match) and assigns that
#   icon name to them automatically. Search roots = $HOME (or SEARCH_ROOT), any EXTRA_ROOTS you set,
#   and -- by default -- every currently mounted disk (internal secondary partitions, external/USB
#   drives, anything under /media, /run/media, /mnt, etc.), auto-detected via findmnt/proc/mounts.
#   Set INCLUDE_MOUNTS=0 to only scan SEARCH_ROOT/EXTRA_ROOTS.
# - Optionally also matches a Russian translation of <word>, for folders that use a Russian name
#   for a generic concept (e.g. "Игры" for "games"). Proper-noun / app names (steam, java, ...) are
#   left alone, since those aren't translated -- only entries you add to the TRANSLATIONS map below
#   get a Russian counterpart searched too.
#
# Using gio to set a custom icon BY NAME (theme resolves the actual SVG):
#       gio set $HOME/Documents/C metadata::custom-icon-name "folder-c"
#
# Then you can confirm the change showing all the attributes with the command:
#       gio info $HOME/Documents/C
# Or showing only custom-icon-name attribute:
#       gio info --attributes="metadata::custom-icon-name" $HOME/Documents/C
# To delete the custom-icon-name attribute use -d flag:
#       gio set $HOME/Documents/C metadata::custom-icon-name -d
#
# Dependencies:
# 	gio
# 	bash 4+ (associative arrays)
#
# --------------------------------------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --------------------------------------------------------------------------------------------------
# Resolve the icon directory relative to THIS script's real location, so it works no matter where
# adw/make/places-generator ends up being installed.

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"

# Force a UTF-8 locale for this run if none is set, so case-insensitive matching against non-ASCII
# folder names (e.g. Cyrillic) works correctly regardless of the calling environment.
if [[ -z "${LC_ALL:-}${LC_CTYPE:-}${LANG:-}" ]] || [[ "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" == "POSIX" || "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" == "C" ]]; then
	export LC_ALL="${LC_ALL:-C.UTF-8}"
fi

COLOR="${COLOR:-blue}"                       # override with: COLOR=teal ./custom_folder_icons.sh
ICONS_DIR="$SCRIPT_DIR/colors/$COLOR"        # used only as a CATALOG of available icon names
SEARCH_ROOT="${SEARCH_ROOT:-$HOME}"          # override with: SEARCH_ROOT=/some/path ./custom_folder_icons.sh
INCLUDE_MOUNTS="${INCLUDE_MOUNTS:-1}"        # 1 = also scan mounted disks, 0 = only SEARCH_ROOT/EXTRA_ROOTS
EXTRA_ROOTS="${EXTRA_ROOTS:-}"               # optional extra paths, colon-separated: /mnt/data:/srv/foo

# Filesystem types to ignore when auto-detecting mounted disks (pseudo/virtual filesystems, not
# real storage a user would keep folders on).
MOUNT_FSTYPE_EXCLUDE_REGEX='^(proc|sysfs|devtmpfs|tmpfs|devpts|cgroup2?|pstore|bpf|configfs|fusectl|binfmt_misc|autofs|mqueue|hugetlbfs|debugfs|tracefs|securityfs|ramfs|squashfs|overlay|nsfs|efivarfs|rpc_pipefs)$'

# --------------------------------------------------------------------------------------------------
# Russian translations for GENERIC words only. App / brand names (steam, java, blender, ...) are
# intentionally NOT listed here -- those stay literal in both languages, so they simply won't get a
# second search term, which is exactly what we want.
# Add more entries as needed: [english_keyword]="russian_word"

declare -A TRANSLATIONS=(
	[games]="игры"
	[music]="музыка"
	[documents]="документы"
	[downloads]="загрузки"
	[pictures]="картинки"
	[photos]="фото"
	[videos]="видео"
	[projects]="проекты"
	[work]="работа"
	[study]="учеба"
	[books]="книги"
	[archive]="архив"
	[backup]="резервная копия"
	[notes]="заметки"
)

# --------------------------------------------------------------------------------------------------

function get_disk_mounts() {
	# Print one real mount point per line: internal secondary partitions, external/USB disks,
	# and anything auto-mounted under /media, /run/media, /mnt -- with pseudo/virtual
	# filesystems (proc, tmpfs, overlay, ...) and core system paths filtered out.
	local target fstype

	if command -v findmnt >/dev/null 2>&1; then
		while read -r target fstype; do
			[[ "$fstype" =~ $MOUNT_FSTYPE_EXCLUDE_REGEX ]] && continue
			case "$target" in
				/ | /boot | /boot/* | /dev | /dev/* | /proc | /proc/* | /sys | /sys/* | /run | /run/* ) continue ;;
			esac
			echo "$target"
		done < <(findmnt -rn -o TARGET,FSTYPE 2>/dev/null)
	elif [ -r /proc/mounts ]; then
		while read -r _device target fstype _rest; do
			[[ "$fstype" =~ $MOUNT_FSTYPE_EXCLUDE_REGEX ]] && continue
			case "$target" in
				/ | /boot | /boot/* | /dev | /dev/* | /proc | /proc/* | /sys | /sys/* | /run | /run/* ) continue ;;
			esac
			echo "$target"
		done < /proc/mounts
	else
		echo -e "${YELLOW}Neither findmnt nor /proc/mounts available -- skipping mounted disk detection${NC}" >&2
	fi
}

function add_root() {
	# Add $1 to SEARCH_ROOTS unless it's already covered by (a subpath of) an existing root; also
	# drops any existing roots that are subpaths of the new one, so we never scan the same folder
	# tree twice.
	local candidate="$1"
	local existing kept=()

	for existing in "${SEARCH_ROOTS[@]}"; do
		case "$candidate" in
			"$existing" | "$existing"/* ) return ;; # already covered, nothing to do
		esac
	done

	for existing in "${SEARCH_ROOTS[@]}"; do
		case "$existing" in
			"$candidate" | "$candidate"/* ) continue ;; # narrower root, superseded by candidate
		esac
		kept+=("$existing")
	done

	SEARCH_ROOTS=("${kept[@]}" "$candidate")
}

function build_search_roots() {
	# Populates the global SEARCH_ROOTS array: SEARCH_ROOT, any EXTRA_ROOTS, and (unless disabled)
	# every currently mounted disk.
	SEARCH_ROOTS=()
	add_root "$SEARCH_ROOT"

	if [ -n "$EXTRA_ROOTS" ]; then
		local IFS=':' extra
		for extra in $EXTRA_ROOTS; do
			[ -d "$extra" ] && add_root "$extra"
		done
	fi

	if [ "$INCLUDE_MOUNTS" -eq 1 ]; then
		local mount_point
		while IFS= read -r mount_point; do
			[ -d "$mount_point" ] && add_root "$mount_point"
		done < <(get_disk_mounts)
	fi
}

function ci() {              # Simplify command
	# $2 here is an ICON NAME (e.g. "folder-projects"), never a path -- GNOME resolves the actual
	# SVG from whichever icon theme is currently active.
	if [[ "$2" == "-d" ]]; then # Delete custom-icon-name attribute
		gio set "$1" metadata::custom-icon-name -d
		echo -e "${GREEN}$1 metadata::custom-icon-name attribute deleted${NC}"
	else # Assign value to custom-icon-name attribute
		gio set "$1" metadata::custom-icon-name "$2"
		echo -e "${GREEN}$1 metadata::custom-icon-name attribute updated to '$2' ${NC}"
	fi
}

function custom-icon() {
	# Manual single assignment, kept for convenience.
	# $1 = folder path, $2 (optional) = icon keyword. If $2 is omitted, uses basename of $1.
	# The catalog (ICONS_DIR) is only consulted to check the icon name is a recognized one; the
	# value actually assigned to the folder is the bare name "folder-<keyword>".
	local target="$1"
	local keyword="${2:-$(basename "$1")}"
	keyword="${keyword,,}"
	local icon_name="folder-${keyword}"
	local catalog_entry="$ICONS_DIR/${icon_name}.svg"

	[ "$del" -eq 1 ] && [ -d "$target" ] && ci "$target" -d && return

	[ ! -d "$target" ] && echo -e "${YELLOW}$target folder does not exist ${NC}" && return
	[ -f "$catalog_entry" ] && ci "$target" "$icon_name"
	[ ! -f "$catalog_entry" ] && echo -e "${RED}$icon_name not found in catalog ($catalog_entry) ${NC}"
}

function auto_assign() {
	# Core feature: for every folder-<word>.svg CATALOG entry, find every folder whose name
	# contains <word> (or its Russian translation, if one is defined) anywhere under any search
	# root -- SEARCH_ROOT, EXTRA_ROOTS, and (unless disabled) every currently mounted disk -- and
	# assign the ICON NAME "folder-<word>" to it -- never a path. The active icon theme is what
	# actually supplies the SVG, in whatever color/variant is installed.

	if [ ! -d "$ICONS_DIR" ]; then
		echo -e "${RED}Icon catalog directory not found: $ICONS_DIR${NC}"
		echo -e "${YELLOW}Expected it next to this script, e.g. <script_dir>/colors/$COLOR${NC}"
		return 1
	fi

	build_search_roots

	echo -e "\nIcon name catalog: $ICONS_DIR (used for discovery only, not for assignment)"
	echo -e "Search roots:"
	local r
	for r in "${SEARCH_ROOTS[@]}"; do echo -e "  - $r"; done
	echo ""

	shopt -s nullglob
	local icon_file base keyword icon_name term terms dir root
	declare -A seen_dirs=() # avoid reapplying the same icon twice when multiple terms/roots match

	for icon_file in "$ICONS_DIR"/folder-*.svg; do
		base="$(basename "$icon_file" .svg)" # folder-java
		keyword="${base#folder-}"            # java
		[ -z "$keyword" ] && continue
		icon_name="folder-${keyword}"        # the NAME assigned to matching folders

		terms=("$keyword")
		[ -n "${TRANSLATIONS[$keyword]:-}" ] && terms+=("${TRANSLATIONS[$keyword]}")

		seen_dirs=()
		for root in "${SEARCH_ROOTS[@]}"; do
			for term in "${terms[@]}"; do
				while IFS= read -r -d '' dir; do
					[ -n "${seen_dirs[$dir]:-}" ] && continue
					seen_dirs["$dir"]=1

					if [ "$del" -eq 1 ]; then
						ci "$dir" -d
					else
						ci "$dir" "$icon_name"
					fi
				done < <(find "$root" -xdev -type d -iname "*${term}*" -not -path "$SCRIPT_DIR*" -print0 2>/dev/null)
			done
		done
	done
	shopt -u nullglob
}

function help() {
	echo -e "\nDescription :"
	echo -e "\tThis script changes folder icons, automatically matching icon NAMES to folder names."
	echo -e "\tOnly the icon NAME (e.g. 'folder-projects') is ever assigned -- never a path to a"
	echo -e "\tspecific SVG -- so the icon shown always comes from whichever icon theme/color is"
	echo -e "\tcurrently active in GNOME, and stays correct if you switch themes later."
	echo -e "\nArguments :"
	echo -e "\t(no args)          auto mode: match every folder-<word> icon NAME (discovered from"
	echo -e "\t                   the catalog) against folder names under \$SEARCH_ROOT (default: \$HOME)"
	echo -e "\t-d                 same as auto mode, but DELETES the custom-icon-name attribute instead"
	echo -e "\t<DIR> <KEYWORD>    manually assign the 'folder-<KEYWORD>' icon NAME to a single folder"
	echo -e "\t-h                 show help"
	echo -e "\nEnvironment overrides :"
	echo -e "\tCOLOR=teal         use <script_dir>/colors/teal as the catalog instead of colors/blue"
	echo -e "\t                   (catalog only decides which icon NAMES exist, not what's assigned)"
	echo -e "\tSEARCH_ROOT=/path  primary search root instead of \$HOME"
	echo -e "\tEXTRA_ROOTS=a:b    extra paths to search too, colon-separated (e.g. /mnt/data:/srv/x)"
	echo -e "\tINCLUDE_MOUNTS=0   disable auto-detection of mounted disks (default: 1, enabled)"
	echo -e "\nBy default every currently mounted disk (secondary partitions, external/USB drives,"
	echo -e "anything under /media, /run/media, /mnt, etc.) is scanned automatically alongside"
	echo -e "\$SEARCH_ROOT -- no extra flags needed."
	echo -e "\nEdit the TRANSLATIONS array near the top of the script to add Russian words for"
	echo -e "generic folder names (games, music, ...). App/brand names are left untranslated."
}

# --------------------------------------------------------------------------------------------------
# Main

del=0
if [ $# -eq 0 ]; then
	auto_assign
elif [ $# -eq 1 ] && [[ "$1" == "-d" ]]; then
	del=1
	auto_assign
elif [ $# -eq 1 ] && [[ "$1" == "-h" ]]; then
	help
elif [ $# -eq 2 ]; then
	custom-icon "$1" "$2"
else
	help
fi