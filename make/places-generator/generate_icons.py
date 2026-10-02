from pathlib import Path
from copy import deepcopy
from lxml import etree
import os
import re

FOLDER = Path("folder")
SYMBOLICS = Path("symbolics")
OUTPUT_ROOT = Path("colors")

SVG_NS = "http://www.w3.org/2000/svg"
GPA_NS = "https://www.gtk.org/grappa"

BASES = {
    "folder": FOLDER / "folder.svg",
    "folder-open": FOLDER / "folder-open.svg",
    "folder-drag-accept": FOLDER / "folder-drag-accept.svg",
    "user-desktop": FOLDER / "user-desktop.svg",
}

SUFFIX = "-symbolic.svg"
FOLDER_PREFIX = "folder-"


def discover_special_icons():
    icons = {}

    for symbolic_file in sorted(SYMBOLICS.glob(f"*{SUFFIX}")):

        stem = symbolic_file.name[: -len(SUFFIX)]

        if stem.startswith(FOLDER_PREFIX):
            short_name = stem[len(FOLDER_PREFIX):]
        else:
            short_name = stem

        if short_name in icons:
            print(
                f"! конфликт имён: '{short_name}' уже занято "
                f"файлом {icons[short_name]}, пропускаю {symbolic_file.name}"
            )
            continue

        icons[short_name] = symbolic_file.name

    return icons


SPECIAL_ICONS = discover_special_icons()

ALIASES = {}

OPEN_ICONS = {
    "documents",
    "download",
    "music",
    "pictures",
    "public",
    "templates",
    "videos",
    "user-home",
}

REFERENCE_SIZE = 128

AREA_X = 32
AREA_Y = 41
AREA_WIDTH = 64
AREA_HEIGHT = 64

MAX_SIZE = 40

SCALE_Y = 1.0

OPEN_PERSPECTIVE = (32, 56, 64, 50, 36, 0.75)

AREA_OVERRIDES = {
    "folder-open": OPEN_PERSPECTIVE,
}


def get_area(base_key):
    return AREA_OVERRIDES.get(
        base_key, (AREA_X, AREA_Y, AREA_WIDTH, AREA_HEIGHT, MAX_SIZE, SCALE_Y)
    )


COLORS = {
    "blue": {"main": "#3a87e5", "light": "#93c0ea"},
    "teal": {"main": "#2190a4", "light": "#53c6d0"},
    "green": {"main": "#3a944a", "light": "#72ba79"},
    "yellow": {"main": "#c88800", "light": "#f5a831"},
    "orange": {"main": "#ed5b00", "light": "#f78754"},
    "red": {"main": "#e62d42", "light": "#e9879a"},
    "pink": {"main": "#d56199", "light": "#e4b0cd"},
    "purple": {"main": "#9141ac", "light": "#b185c6"},
    "slate": {"main": "#6f8396", "light": "#acb2b6"},
}

BASE_MAIN = "#438DE6"
BASE_LIGHT = "#A4CAEE"

BASE_GRADIENT = {
    "#62a0ea": ("main", 0.165),
    "#afd4ff": ("light", 0.15),
    "#c0d5ea": ("light", 0.20),
    "#b9d6f2": ("light", 0.23),
}

PER_COLOR_ALIASES = [
    ("folder-downloads", "folder-download"),
    ("folder-desktop", "user-desktop"),
    ("folder-public", "folder-image-people"),
    ("folder-videos", "folder-video"),
    ("folder-images", "folder-pictures"),
    ("folder-photos", "folder-photo"),
]

GLOBAL_ALIASES = [
    ("desktop", "user-desktop"),
    ("certificate-server", "folder-locked"),
    ("gtk-directory", "folder"),
    ("inode-directory", "folder"),
    ("stock_folder", "folder"),
    ("stock_open", "folder-open"),
    ("folder_open", "folder-open"),
    ("gtk-network", "folder-network"),
    ("network", "folder-network"),
    ("repository", "folder-network"),
    ("knetattach", "folder-remote"),
    ("library-music", "folder-music"),
    ("insync-folder", "folder-google-drive"),
    ("gnome-home", "user-home"),
    ("folder-home", "user-home"),
    ("folder_home", "user-home"),
    ("folder_home2", "folder-image-people"),
    ("folder-text", "folder-documents"),
    ("folder-txt", "folder-documents"),
    ("folder_man", "folder-documents"),
    ("folder_wordprocessing", "folder-documents"),
    ("folder-temp", "folder-recent"),
    ("folder-encrypted", "folder-locked"),
    ("folder-decrypted", "folder-unlocked"),
    ("folder-camera", "folder-photo"),
    ("folder-picture", "folder-pictures"),
    ("folder-image", "folder-images"),
    ("folder-sound", "folder-music"),
    ("folder-videocamera", "folder-video"),
    ("folder-gdrive", "folder-google-drive"),
    ("folder-cloud", "folder-mail-cloud"),
    ("folder-html", "folder-network"),
]

PAINT_ATTRS = ("fill", "stroke", "stop-color")
SKIPPED_TAGS = ("defs", "namedview", "metadata", "title", "desc")
BLACK_VALUES = {"#000", "#000000", "black", "rgb(0,0,0)"}
STYLE_PAINT_RE = re.compile(
    r"(fill|stroke|stop-color)\s*:\s*"
    r"(currentColor|#000000|#000|black|rgb\(\s*0\s*,\s*0\s*,\s*0\s*\))",
    re.IGNORECASE,
)


def parse_svg(path):
    return etree.parse(str(path))


def parse_length(value: str):
    if value is None:
        return None

    match = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*([a-z%]*)\s*$", value.strip(), re.IGNORECASE)

    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2).lower()

    UNIT_TO_PX = {
        "": 1.0,
        "px": 1.0,
        "pt": 96 / 72,
        "pc": 16.0,
        "in": 96.0,
        "mm": 96 / 25.4,
        "cm": 96 / 2.54,
    }

    if unit in UNIT_TO_PX:
        return number * UNIT_TO_PX[unit]

    return None


def get_viewbox(root):
    vb = root.get("viewBox")

    if vb:
        return tuple(map(float, vb.replace(",", " ").split()))

    width = parse_length(root.get("width"))
    height = parse_length(root.get("height"))

    if width is not None and height is not None:
        print(f"  ! нет viewBox, восстановлен из width/height: 0 0 {width} {height}")
        return (0.0, 0.0, width, height)

    print("  ! нет ни viewBox, ни пригодных width/height — использую дефолт 24x24")
    return (0.0, 0.0, 24.0, 24.0)


def _hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _mix_with_white(value, amount):
    r, g, b = _hex_to_rgb(value)
    r, g, b = (round(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def build_color_map(main_color, light_color):
    mapping = {
        BASE_MAIN.lower(): main_color,
        BASE_LIGHT.lower(): light_color,
    }

    theme = {"main": main_color, "light": light_color}

    for old, (which, amount) in BASE_GRADIENT.items():
        mapping[old.lower()] = _mix_with_white(theme[which], amount)

    return mapping


def replace_colors(text, mapping):
    pattern = re.compile("|".join(re.escape(k) for k in mapping), re.IGNORECASE)
    return pattern.sub(lambda m: mapping[m.group(0).lower()], text)


def recolor_folder(root, main_color, light_color):
    mapping = build_color_map(main_color, light_color)

    for element in root.iter():

        if not isinstance(element.tag, str):
            continue

        if etree.QName(element).localname == "style" and element.text:
            element.text = replace_colors(element.text, mapping)

        for attr in ("fill", "stroke", "stop-color", "style"):
            value = element.get(attr)

            if value:
                element.set(attr, replace_colors(value, mapping))


def _is_symbolic_paint(value):
    normalized = re.sub(r"\s+", "", value).lower()
    return normalized == "currentcolor" or normalized in BLACK_VALUES


def recolor_symbolic(root, color):
    for element in root.iter():

        if not isinstance(element.tag, str):
            continue

        for attr in PAINT_ATTRS:
            value = element.get(attr)

            if value and _is_symbolic_paint(value):
                element.set(attr, color)

        for attr in list(element.attrib):
            if attr.startswith(f"{{{GPA_NS}}}"):
                del element.attrib[attr]

        style = element.get("style")

        if style:
            element.set("style", STYLE_PAINT_RE.sub(lambda m: f"{m.group(1)}:{color}", style))


def create_symbolic(symbolic_root, color, base_key, base_root):
    area_x, area_y, area_w, area_h, max_size, scale_y = get_area(base_key)

    base_vb_w = get_viewbox(base_root)[2]

    if base_vb_w <= 0:
        raise ValueError("некорректный viewBox базового шаблона")

    k = base_vb_w / REFERENCE_SIZE
    area_x, area_y, area_w, area_h, max_size = (
        v * k for v in (area_x, area_y, area_w, area_h, max_size)
    )

    vb_x, vb_y, vb_w, vb_h = get_viewbox(symbolic_root)

    if vb_w <= 0 or vb_h <= 0:
        raise ValueError(f"некорректный viewBox: {vb_x} {vb_y} {vb_w} {vb_h}")

    scale = max_size / max(vb_w, vb_h)

    width = vb_w * scale
    height = vb_h * scale * scale_y

    x = area_x + (area_w - width) / 2
    y = area_y + (area_h - height) / 2

    group = etree.Element(
        f"{{{SVG_NS}}}g",
        transform=(
            f"translate({x:.4f},{y:.4f}) "
            f"scale({scale:.6f},{scale * scale_y:.6f}) "
            f"translate({-vb_x:.4f},{-vb_y:.4f})"
        ),
    )

    recolor_symbolic(symbolic_root, color)

    for child in symbolic_root:

        if not isinstance(child.tag, str):
            continue

        if etree.QName(child).localname in SKIPPED_TAGS:
            continue

        group.append(deepcopy(child))

    etree.cleanup_namespaces(group)

    return group


def load_recolored_base(base_path, main_color, light_color):
    tree = parse_svg(base_path)
    root = tree.getroot()
    recolor_folder(root, main_color, light_color)
    return root


def write_svg(root, path):
    etree.ElementTree(root).write(
        str(path),
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True,
    )


GENERATED = {}

FAILED = []


def make_plain_icon(base_key, base_name, main_color, light_color, output_dir):
    root = load_recolored_base(BASES[base_key], main_color, light_color)
    output_file = output_dir / f"{base_name}.svg"
    write_svg(root, output_file)
    GENERATED.setdefault(output_dir, set()).add(base_name)
    print(f"✓ {output_file}")


def make_special_icon(base_key, short_name, symbolic_filename, suffix, main_color, light_color, output_dir):
    symbolic_path = SYMBOLICS / symbolic_filename

    if not symbolic_path.exists():
        print(f"! пропуск: нет файла {symbolic_path}")
        FAILED.append((symbolic_filename, "файл не найден"))
        return

    try:
        symbolic_tree = parse_svg(symbolic_path)
        symbolic_root = symbolic_tree.getroot()
    except Exception as e:
        print(f"! пропуск {symbolic_filename}: не удалось распарсить XML ({e})")
        FAILED.append((symbolic_filename, f"ошибка парсинга: {e}"))
        return

    root = load_recolored_base(BASES[base_key], main_color, light_color)

    try:
        symbolic_group = create_symbolic(symbolic_root, main_color, base_key, root)
    except Exception as e:
        print(f"! пропуск {symbolic_filename}: {e}")
        FAILED.append((symbolic_filename, str(e)))
        return

    root.append(symbolic_group)

    result_name = ALIASES.get(short_name, short_name)
    out_name = f"folder-{result_name}{suffix}"

    output_file = output_dir / f"{out_name}.svg"
    write_svg(root, output_file)
    GENERATED.setdefault(output_dir, set()).add(out_name)
    print(f"✓ {output_file}")


def make_symlink(output_dir: Path, link_name: str, target_name: str):
    if link_name == target_name:
        return

    link_path = output_dir / f"{link_name}.svg"
    target_filename = f"{target_name}.svg"
    target_path = output_dir / target_filename

    generated_here = GENERATED.get(output_dir, set())

    if target_name not in generated_here and not target_path.exists():
        print(f"! пропуск symlink {output_dir.name}/{link_name}.svg -> {target_filename}: цели нет")
        return

    if link_path.is_symlink() or link_path.exists():
        if link_path.is_symlink() and os.readlink(link_path) == target_filename:
            return
        link_path.unlink()

    link_path.symlink_to(target_filename)
    print(f"→ {output_dir.name}/{link_path.name} -> {target_filename}")


open_count = sum(
    1 for short_name in SPECIAL_ICONS
    if ALIASES.get(short_name, short_name) in OPEN_ICONS
)

print(f"Найдено symbolic-эмблем: {len(SPECIAL_ICONS)}")
print(f"  из них с открытым вариантом: {open_count}")
print()

OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

for color_name, colors in COLORS.items():

    output_dir = OUTPUT_ROOT / color_name
    output_dir.mkdir(parents=True, exist_ok=True)

    main_color = colors["main"]
    light_color = colors["light"]

    print(f"== {color_name} -> {output_dir} ==")

    make_plain_icon("folder", "folder", main_color, light_color, output_dir)
    make_plain_icon("folder-open", "folder-open", main_color, light_color, output_dir)
    make_plain_icon("folder-drag-accept", "folder-drag-accept", main_color, light_color, output_dir)
    make_plain_icon("user-desktop", "user-desktop", main_color, light_color, output_dir)

    for short_name, symbolic_filename in SPECIAL_ICONS.items():

        result_name = ALIASES.get(short_name, short_name)

        make_special_icon(
            "folder", short_name, symbolic_filename, "",
            main_color, light_color, output_dir,
        )

        if result_name in OPEN_ICONS:
            make_special_icon(
                "folder-open", short_name, symbolic_filename, "-open",
                main_color, light_color, output_dir,
            )

    for alias_base, target_base in PER_COLOR_ALIASES:
        make_symlink(output_dir, alias_base, target_base)

    for alias_name, target_base in GLOBAL_ALIASES:
        make_symlink(output_dir, alias_name, target_base)

    print()

print("Готово.")

if FAILED:
    print(f"\nПроблемных symbolic-файлов: {len(FAILED)}")
    for name, reason in FAILED:
        print(f"  - {name}: {reason}")
