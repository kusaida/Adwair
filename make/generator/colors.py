from pathlib import Path
from copy import deepcopy
from lxml import etree
from PIL import Image
import base64
import colorsys
import io
import math
import os
import re

FOLDER = Path("folder")
SYMBOLICS = Path("symbolics")
OUTPUT_ROOT = Path("colors")

APPS = Path("apps")
APP_OUTPUT_ROOT = APPS

APP_ICONS = ["file-manager"]

RED = [(340, 360, 0.5), (0, 12, 0.5)]
BLUE = (195, 235, 0.45)

APP_SPEC = {
    "calc":                    [(195, 240, 0.4)],
    "gnome-tweak-tool":        [BLUE],
    "internet-mail":           [(195, 235, 0.5)],
    "page.tesk.Refine":        [(195, 235, 0.5)],
    "softwarecenter":          [(195, 235, 0.5)],
    "software-properties":     [(195, 235, 0.5)],
    "system-file-manager":     [(195, 235, 0.25)],
    "calendar":                RED,
    "cheese":                  [(175, 200, 0.8)],
    "extensions":              [(125, 150, 0.5)],
    "gnome-books":             [(265, 295, 0.3)],
    "gnome-music":             [(335, 350, 0.8)],
    "gnome-sound-recorder":    [(350, 360, 0.9), (0, 10, 0.9)],
    "preferences-system-time": RED,
}

APP_PALETTE = {
    "yellow": ("#f5a831", "#f9c46a"),
}

APP_COLOR_OVERRIDES = {
    "softwarecenter":      {"red": {"light": "#e94c5e"}},
    "software-properties": {"red": {"light": "#e94c5e"}},
}

APP_TWEAKS = {
    "slate": {"spread": 1.5, "chroma": 1.7},
}

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
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


PNG_DATA_PREFIX = "data:image/png;base64,"

GLOW_BASE = "#62a0ea"

TINT_MIN_SATURATION = 0.25


def _is_colored_png(img):
    saturation = img.convert("RGB").convert("HSV").getchannel("S")
    alpha = img.getchannel("A")

    total = 0
    weighted = 0

    for s, a in zip(saturation.getdata(), alpha.getdata()):
        total += a
        weighted += s * a

    if total == 0:
        return False

    return weighted / total / 255 > TINT_MIN_SATURATION


def recolor_embedded_images(root, main_color, light_color):
    tint = build_color_map(main_color, light_color)[GLOW_BASE]
    tint_rgb = _hex_to_rgb(tint)

    for element in root.iter(f"{{{SVG_NS}}}image"):

        key = f"{{{XLINK_NS}}}href" if element.get(f"{{{XLINK_NS}}}href") else "href"
        href = element.get(key)

        if not href or not href.startswith(PNG_DATA_PREFIX):
            continue

        img = Image.open(io.BytesIO(base64.b64decode(href[len(PNG_DATA_PREFIX):]))).convert("RGBA")

        if not _is_colored_png(img):
            continue

        tinted = Image.new("RGBA", img.size, tint_rgb + (255,))
        tinted.putalpha(img.getchannel("A"))

        buffer = io.BytesIO()
        tinted.save(buffer, format="PNG", optimize=True)

        element.set(key, PNG_DATA_PREFIX + base64.b64encode(buffer.getvalue()).decode("ascii"))


def strip_metadata(root):
    for element in list(root):
        if isinstance(element.tag, str) and etree.QName(element).localname == "metadata":
            root.remove(element)

    etree.cleanup_namespaces(root)


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


def make_app_icon(app_name, color_name, main_color, light_color):
    source = APPS / f"{app_name}.svg"

    if not source.exists():
        print(f"! пропуск: нет файла {source}")
        FAILED.append((source.name, "файл не найден"))
        return

    try:
        root = load_recolored_base(source, main_color, light_color)
        recolor_embedded_images(root, main_color, light_color)
        strip_metadata(root)
    except Exception as e:
        print(f"! пропуск {source.name}: {e}")
        FAILED.append((source.name, str(e)))
        return

    output_dir = APP_OUTPUT_ROOT / color_name
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{app_name}.svg"
    write_svg(root, output_file)
    print(f"✓ {output_file}")


HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")

HIGHLIGHT_L = 0.85

RGB_RE = re.compile(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", re.IGNORECASE)


def rgb_to_hex_text(text):
    return RGB_RE.sub(
        lambda m: "#%02x%02x%02x" % tuple(min(int(v), 255) for v in m.groups()), text
    )


def norm_hex(raw):
    raw = raw.lstrip("#").lower()
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    return "#" + raw


def hex_to_hls(value):
    r, g, b = (int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


def in_window(value, windows):
    h, l, s = hex_to_hls(value)
    deg = h * 360
    for w in windows:
        hmin, hmax, smin = w[0], w[1], w[2]
        lmin, lmax = (w[3], w[4]) if len(w) > 3 else (0.0, 1.0)
        hue_ok = hmin <= deg <= hmax if hmin <= hmax else (deg >= hmin or deg <= hmax)
        if hue_ok and s >= smin and lmin <= l <= lmax:
            return True
    return False


def find_accent_colors(text, windows):
    found = {}
    for raw in HEX_RE.findall(text):
        value = norm_hex(raw)
        if in_window(value, windows):
            found[value] = found.get(value, 0) + 1
    return found


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    c = min(max(c, 0.0), 1.0)
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_to_oklab(value):
    r, g, b = (_lin(int(value[i:i + 2], 16) / 255) for i in (1, 3, 5))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _oklab_rgb(L, a, b):
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def oklab_to_hex(L, a, b):
    L = min(max(L, 0.0), 1.0)
    k = 1.0
    for _ in range(24):
        rgb = _oklab_rgb(L, a * k, b * k)
        if all(-0.002 <= c <= 1.002 for c in rgb):
            break
        k *= 0.92
    return "#%02x%02x%02x" % tuple(round(_gam(c) * 255) for c in rgb)


SHAPE_TAGS = {"path", "rect", "circle", "ellipse", "polygon", "polyline", "line", "text", "use"}
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def _style_value(element, name):
    value = element.get(name)
    style = element.get("style")
    if style:
        m = re.search(rf"(?:^|;)\s*{name}\s*:\s*([^;]+)", style)
        if m:
            value = m.group(1).strip()
    return value


def _number(value, default=1.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def color_visibility(text):
    try:
        root = etree.fromstring(text.encode("utf-8"))
    except Exception:
        return {}

    gradients = {}
    for g in root.iter():
        if not isinstance(g.tag, str) or etree.QName(g).localname not in ("linearGradient", "radialGradient"):
            continue
        stops = []
        for stop in g:
            if isinstance(stop.tag, str) and etree.QName(stop).localname == "stop":
                color = _style_value(stop, "stop-color")
                if color and HEX_RE.fullmatch(color.strip()):
                    stops.append(norm_hex(color.strip()))
        gradients[g.get("id")] = (stops, (g.get(XLINK_HREF) or "").lstrip("#"))

    def stops_of(gid, depth=0):
        stops, parent = gradients.get(gid, ([], ""))
        if not stops and parent and depth < 5:
            return stops_of(parent, depth + 1)
        return stops

    vis = {}

    def walk(element, inherited):
        if not isinstance(element.tag, str):
            return
        local = etree.QName(element).localname
        if local in ("defs", "style", "metadata", "title", "desc", "linearGradient", "radialGradient"):
            return
        weight = inherited * min(_number(_style_value(element, "opacity")), 1.0)
        if element.get("filter") or (element.get("style") and "filter" in element.get("style")):
            weight *= 0.4
        if local in SHAPE_TAGS:
            for attr, mult in (("fill", 1.0), ("stroke", 0.6)):
                value = _style_value(element, attr)
                if not value or value == "none":
                    continue
                value = value.strip()
                w = weight * mult * min(_number(_style_value(element, f"{attr}-opacity")), 1.0)
                m = re.fullmatch(r"url\(#([^)]+)\)", value)
                colors = stops_of(m.group(1)) if m else ([norm_hex(value)] if HEX_RE.fullmatch(value) else [])
                for c in colors:
                    vis[c] = max(vis.get(c, 0.0), w)
        for child in element:
            walk(child, weight)

    walk(root, 1.0)
    return vis


def build_map_inherit(accent, target_main, vis=None, spread=1.0, chroma=1.0):
    if not accent:
        return {}
    vis = vis or {}
    tL, ta, tb = hex_to_oklab(target_main)
    t_chroma, t_hue = math.hypot(ta, tb), math.atan2(tb, ta)
    lab = {c: hex_to_oklab(c) for c in accent}

    def pick(lo, hi):
        return [c for c in accent if lo <= lab[c][0] <= hi and vis.get(c, 1.0) >= 0.6]

    body = pick(0.4, 0.82) or pick(0.25, 0.92) or \
           [c for c in accent if 0.4 <= lab[c][0] <= 0.82] or list(accent)
    l_ref = sum(lab[c][0] for c in body) / len(body)
    c_ref = sum(math.hypot(*lab[c][1:]) for c in body) / len(body) or 1.0

    mapping = {}
    for c in accent:
        L, a, b = lab[c]
        if L > HIGHLIGHT_L:
            new_l = L
        else:
            new_l = tL + (L - l_ref) * spread
        ratio = min(max(math.hypot(a, b) / c_ref, 0.1), 1.0)
        nc = t_chroma * chroma * ratio
        mapping[c] = oklab_to_hex(new_l, nc * math.cos(t_hue), nc * math.sin(t_hue))
    return mapping


def replace_accent_colors(text, mapping):
    return HEX_RE.sub(lambda m: mapping.get(norm_hex(m.group(0)), m.group(0)), text)


def strip_metadata_text(text):
    return re.sub(r"<metadata\b.*?</metadata>", "", text, flags=re.S)


def prepare_app_accents():
    accents = {}

    for app_name, windows in APP_SPEC.items():

        if app_name in APP_ICONS:
            continue

        source = APPS / f"{app_name}.svg"

        if not source.exists():
            print(f"! пропуск: нет файла {source}")
            FAILED.append((source.name, "файл не найден"))
            continue

        text = rgb_to_hex_text(strip_metadata_text(source.read_text(encoding="utf-8", errors="ignore")))
        accent = find_accent_colors(text, windows)

        if not accent:
            print(f"! {app_name}: акцентные цвета не найдены — проверьте окна в APP_SPEC")
            FAILED.append((source.name, "акцентные цвета не найдены"))
            continue

        accents[app_name] = (text, accent, color_visibility(text))
        print(f"✓ {app_name}: акцентных цветов — {len(accent)}")

    return accents


def make_accent_app_icon(app_name, text, accent, vis, color_name, main_color):
    mapping = build_map_inherit(accent, main_color, vis, **APP_TWEAKS.get(color_name, {}))

    override = APP_COLOR_OVERRIDES.get(app_name, {}).get(color_name, {})

    if "light" in override:
        body = [
            c for c in accent
            if hex_to_oklab(c)[0] <= HIGHLIGHT_L and vis.get(c, 1.0) >= 0.6
        ] or list(accent)
        lightest = max(body, key=lambda c: hex_to_oklab(c)[0])
        mapping[lightest] = override["light"].lower()

    output_dir = APP_OUTPUT_ROOT / color_name
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{app_name}.svg"
    output_file.write_text(replace_accent_colors(text, mapping), encoding="utf-8")
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

APP_ACCENTS = prepare_app_accents()
print()

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

    app_main, app_light = APP_PALETTE.get(color_name, (main_color, light_color))

    for app_name in APP_ICONS:
        make_app_icon(app_name, color_name, app_main, app_light)

    for app_name, (app_text, app_accent, app_vis) in APP_ACCENTS.items():
        make_accent_app_icon(app_name, app_text, app_accent, app_vis, color_name, app_main)

    print()

print("Готово.")

if FAILED:
    print(f"\nПроблемных symbolic-файлов: {len(FAILED)}")
    for name, reason in FAILED:
        print(f"  - {name}: {reason}")
