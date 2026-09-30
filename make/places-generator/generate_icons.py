from pathlib import Path
from copy import deepcopy
from lxml import etree
import os
import re

FOLDER = Path("folder")
SYMBOLICS = Path("symbolics")
OUTPUT_ROOT = Path("colors")  # внутри будет output/pink и output/slate

SVG_NS = "http://www.w3.org/2000/svg"

# -----------------------------------------------------------------
# Базовые шаблоны (уже нарисованные вручную, НЕ генерируются)
# ВАЖНО: эти файлы должны быть окрашены в BASE_MAIN/BASE_LIGHT
# (синий), т.к. recolor_folder() ищет именно эти hex-значения,
# чтобы заменить их на цвет темы.
# -----------------------------------------------------------------
BASES = {
    "folder": FOLDER / "folder.svg",
    "folder-open": FOLDER / "folder-open.svg",
    "folder-drag-accept": FOLDER / "folder-drag-accept.svg",
    "user-desktop": FOLDER / "user-desktop.svg",
}

# -----------------------------------------------------------------
# Спецпапки собираются АВТОМАТИЧЕСКИ из всех файлов в SYMBOLICS
# -----------------------------------------------------------------
SUFFIX = "-symbolic.svg"
FOLDER_PREFIX = "folder-"


def discover_special_icons():
    """Сканирует SYMBOLICS и строит словарь: короткое-имя -> имя файла эмблемы."""

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

# -----------------------------------------------------------------
# Переименования при генерации: короткое-имя (ключ SPECIAL_ICONS)
# -> имя, которое должно оказаться в имени итогового файла.
# Не создаёт symlink — просто меняет, под каким именем эмблема
# будет нарисована. Пустой словарь = без переименований.
# -----------------------------------------------------------------
ALIASES = {
    # "downloads": "download",
    # "public": "image-people",
}

# -----------------------------------------------------------------
# Отдельная "-open" версия нужна ТОЛЬКО для этих иконок (сверяются
# уже ПОСЛЕ применения ALIASES, т.е. по итоговому короткому имени).
# -----------------------------------------------------------------
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

# Все размеры ниже заданы в координатах эталонного холста 128x128.
# Скрипт сам пересчитывает их под фактический viewBox каждого шаблона
# (64x64, 128x128, 256x256 ...), так что при смене размера шаблонов
# ничего подгонять не нужно.
REFERENCE_SIZE = 128

# Область символики на закрытой папке: передняя панель x 12..116,
# y 40..106, центр по X = 64, центр по Y = 73.
AREA_X = 32
AREA_Y = 41
AREA_WIDTH = 64
AREA_HEIGHT = 64

# Максимальный размер символики
MAX_SIZE = 40

# Вертикальное сжатие эмблемы (1.0 = без сжатия). Имитирует перспективу:
# у "приоткрытых" шаблонов передняя панель наклонена к зрителю, поэтому
# плоская эмблема на ней выглядит сплюснутой по вертикали.
SCALE_Y = 1.0

# Перспектива "приоткрытой" папки. Образец геометрии — folder-drag-accept:
# передняя панель короче и опущена (тело панели y 55..108, центр по Y ~ 81),
# поэтому эмблема ужимается по вертикали до 75%.
#   (x, y, width, height, max_size, scale_y)
OPEN_PERSPECTIVE = (32, 56, 64, 50, 36, 0.75)

# Свои параметры для шаблонов, у которых панель расположена иначе:
#   "ключ из BASES": (x, y, width, height, max_size, scale_y)
# Всё, что не указано, использует значения выше.
AREA_OVERRIDES = {
    "folder-open": OPEN_PERSPECTIVE,
}


def get_area(base_key):
    return AREA_OVERRIDES.get(
        base_key, (AREA_X, AREA_Y, AREA_WIDTH, AREA_HEIGHT, MAX_SIZE, SCALE_Y)
    )


# -----------------------------------------------------------------
# Только два цвета темы. Каждый цвет пишется в свою собственную
# подпапку output/<color>/, поэтому в именах файлов цвет больше
# не указывается вообще (никакой "folder-pink-..." — просто
# "folder-...").
# -----------------------------------------------------------------
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
# Цвета, зашитые в базовые шаблоны (folder/*.svg), которые
# recolor_folder() ищет и заменяет на цвет текущей темы.
# Совпадают с классами .s0 / .s4 в folder/folder.svg.
BASE_MAIN = "#438DE6"
BASE_LIGHT = "#A4CAEE"

# Производные цвета шаблонов (градиент g1 и светлая кромка .s3 в
# folder-drag-accept). Каждый — это цвет темы, смешанный с белым в
# указанной пропорции (подобрано под синий шаблон).
BASE_GRADIENT = {
    "#62a0ea": ("main", 0.165),
    "#afd4ff": ("light", 0.15),
    "#c0d5ea": ("light", 0.20),
    "#b9d6f2": ("light", 0.23),
}

# -----------------------------------------------------------------
# Алиасы, которые создаются РЕАЛЬНЫМИ symlink'ами (не копиями файла),
# как в настоящей Papirus. Каждая пара — "базовые" имена без .svg.
# Пересоздаются внутри КАЖДОЙ цветовой подпапки, т.к. цвет теперь
# определяется папкой, а не именем файла.
#
# Примеры того, что получится (внутри output/pink/ и output/slate/):
#   folder-downloads.svg -> folder-download.svg
#   folder-desktop.svg   -> user-desktop.svg
#
# Дополняйте список любыми парами, которых не хватает —
# отсутствующая цель просто даст предупреждение, а не ошибку.
# -----------------------------------------------------------------
PER_COLOR_ALIASES = [
    ("folder-downloads", "folder-download"),
    ("folder-desktop", "user-desktop"),
    ("folder-public", "folder-image-people"),
    ("folder-videos", "folder-video"),
    ("folder-images", "folder-pictures"),
    ("folder-photos", "folder-photo"),
]

# -----------------------------------------------------------------
# Раньше эти алиасы были "глобальными" (без цвета — ссылались на
# цвет темы по умолчанию). Теперь единой темы по умолчанию нет:
# оба цвета равноправны, каждый в своей папке. Поэтому эти алиасы
# ТОЖЕ пересоздаются внутри КАЖДОЙ цветовой подпапки и ссылаются
# на файл того же цвета (той же папки).
# -----------------------------------------------------------------
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
    # ("folder-root", "folder-red"),  # "red" больше не генерируется как цвет темы
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


def parse_svg(path):
    return etree.parse(str(path))


def parse_length(value: str):
    """
    Парсит строку вида '24', '24px', '24.0pt', '1in' и возвращает
    число в "пользовательских единицах" (px как 1:1, остальное
    переводится приблизительно по 96 DPI). Возвращает None, если
    распарсить не удалось (например, единица '%').
    """

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

    # '%' или неизвестная единица — не можем надёжно перевести
    return None


def get_viewbox(root):
    """
    Возвращает (x, y, w, h). Если атрибут viewBox отсутствует —
    пытается восстановить его из width/height. Если и их нет
    (или они в непереводимых единицах, например '%') — использует
    дефолт 24x24, типичный для symbolic-иконок.
    """

    vb = root.get("viewBox")

    if vb:
        return tuple(map(float, vb.split()))

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
    """Словарь {старый hex (нижний регистр): новый hex} для одной темы."""

    mapping = {
        BASE_MAIN.lower(): main_color,
        BASE_LIGHT.lower(): light_color,
    }

    theme = {"main": main_color, "light": light_color}

    for old, (which, amount) in BASE_GRADIENT.items():
        mapping[old.lower()] = _mix_with_white(theme[which], amount)

    return mapping


def replace_colors(text, mapping):
    """Заменяет все hex-цвета из mapping за один проход, без учёта регистра."""

    pattern = re.compile("|".join(re.escape(k) for k in mapping), re.IGNORECASE)
    return pattern.sub(lambda m: mapping[m.group(0).lower()], text)


def recolor_folder(root, main_color, light_color):
    """
    Перекрашивает шаблон папки. Цвета могут лежать в трёх местах:
    в блоке <style> (классы .s0, .s4 ...), в атрибутах fill / stop-color
    и в атрибуте style. Обрабатываем все три.
    """

    mapping = build_color_map(main_color, light_color)

    for element in root.iter():

        if not isinstance(element.tag, str):
            continue  # комментарии и т.п.

        if etree.QName(element).localname == "style" and element.text:
            element.text = replace_colors(element.text, mapping)

        for attr in ("fill", "stroke", "stop-color", "style"):
            value = element.get(attr)

            if value:
                element.set(attr, replace_colors(value, mapping))


def recolor_symbolic(root, color):
    """Symbolic использует currentColor. Заменяем его на основной цвет папки."""

    for element in root.iter():
        fill = element.get("fill")

        if fill == "currentColor":
            element.set("fill", color)

        style = element.get("style")

        if style:
            style = style.replace("fill:currentColor", f"fill:{color}")
            style = style.replace("fill: currentColor", f"fill: {color}")
            element.set("style", style)


def create_symbolic(symbolic_root, color, base_key, base_root):
    """Масштабирует symbolic и центрирует его в заданной области папки."""

    area_x, area_y, area_w, area_h, max_size, scale_y = get_area(base_key)

    # Пересчёт эталонных 128x128 в координаты viewBox шаблона
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
        tag = etree.QName(child).localname

        if tag in ("defs", "namedview"):
            continue

        group.append(deepcopy(child))

    return group


def load_recolored_base(base_path, main_color, light_color):
    """Загружает базовый шаблон и красит его в нужный цвет."""

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


# Что реально сгенерировано в этом запуске, отдельно по каждой
# цветовой подпапке: {output_dir: {"folder", "folder-documents", ...}}
# Нужно, чтобы make_symlink мог проверить существование цели.
GENERATED = {}

# Файлы, которые не удалось обработать (для итогового отчёта)
FAILED = []


def make_plain_icon(base_key, base_name, main_color, light_color, output_dir):
    """Просто красит базовый шаблон, без эмблемы. Имя файла без цвета."""

    root = load_recolored_base(BASES[base_key], main_color, light_color)
    output_file = output_dir / f"{base_name}.svg"
    write_svg(root, output_file)
    GENERATED.setdefault(output_dir, set()).add(base_name)
    print(f"✓ {output_file}")


def make_special_icon(base_key, short_name, symbolic_filename, suffix, main_color, light_color, output_dir):
    """Красит базовый шаблон и накладывает поверх symbolic-эмблему. Имя файла без цвета."""

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
    """
    Создаёт настоящий относительный symlink link_name.svg -> target_name.svg
    внутри output_dir (т.е. внутри конкретной цветовой подпапки).
    Пропускает, если имена совпадают, и предупреждает, если цель ещё
    не сгенерирована и не существует на диске.
    """

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

    # ---------------------------------------------------------
    # 1. Базовые иконки без эмблем
    # ---------------------------------------------------------
    make_plain_icon("folder", "folder", main_color, light_color, output_dir)
    make_plain_icon("folder-open", "folder-open", main_color, light_color, output_dir)
    make_plain_icon("folder-drag-accept", "folder-drag-accept", main_color, light_color, output_dir)
    make_plain_icon("user-desktop", "user-desktop", main_color, light_color, output_dir)

    # ---------------------------------------------------------
    # 2. Спецпапки: закрытый вариант — всегда,
    #    открытый — только если имя есть в OPEN_ICONS
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 3. Симлинки-алиасы для этой цветовой подпапки
    #    (и "per-color", и бывшие "global" — оба набора теперь
    #    пересоздаются в каждой подпапке отдельно)
    # ---------------------------------------------------------
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
