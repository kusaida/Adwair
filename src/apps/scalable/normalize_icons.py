#!/usr/bin/env python3
"""
normalize_icons.py

Заменяет ТОЛЬКО тёмный/чёрный фон SVG-иконок на фон, взятый 1:1 из
эталонного app-template-black.svg. Иконки с цветным фоном (синим,
зелёным, красным, жёлтым, оранжевым и т.п.) не изменяются.

Алгоритм и флаги описаны в сообщении, которым передан этот файл.
"""

import argparse
import base64
import copy
import io
import re
import shutil
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

GRAPHIC_TAGS = {
    "rect", "path", "circle", "ellipse", "polygon", "polyline",
    "image", "use",
}

DARK_MAX_LUMA = 120.0
# Насколько "серым" должен быть цвет, чтобы считаться чёрным/тёмным фоном,
# а не просто тёмным оттенком синего/красного/зелёного и т.п.
# HSL saturation в диапазоне 0..1. Тёмно-синий (#0d47a1, s~0.86) и
# тёмно-бордовый (#400000, s~1.0) отсекаются этим порогом; #363636/#6c6c6c
# (s=0) проходят.
MAX_SATURATION = 0.18
CANVAS_DEFAULT = 64.0


# ---------------------------------------------------------------- helpers --

def tag_name(el):
    return el.tag.rsplit("}", 1)[-1]


def num(value):
    if not value:
        return None
    m = re.match(r"\s*(-?(?:\d+(?:\.\d*)?|\.\d+))", value)
    return float(m.group(1)) if m else None


def parse_color(value):
    """RGB для #rgb / #rrggbb / rgb(r,g,b)."""
    if not value:
        return None
    value = value.strip().lower()

    if value.startswith("#"):
        h = value[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6 and all(c in "0123456789abcdef" for c in h):
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    m = re.fullmatch(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", value)
    if m:
        return tuple(int(x) for x in m.groups())

    return None


def luminance(rgb):
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def saturation(rgb):
    """HSL saturation, 0..1. 0 = чистый серый/чёрный/белый, 1 = максимально насыщенный цвет."""
    r, g, b = (c / 255.0 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return 0.0
    l = (mx + mn) / 2
    d = mx - mn
    return d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)


def colors_are_dark_neutral(rgbs):
    """
    True/False/None по списку RGB-цветов (для solid fill - список из одного).
    Тёмным ЧЁРНЫМ/СЕРЫМ фоном считается только то, что одновременно:
      - достаточно тёмное (средняя яркость <= DARK_MAX_LUMA), И
      - достаточно нейтральное/серое (средняя насыщенность <= MAX_SATURATION).
    Просто "тёмный синий/красный/зелёный" не пройдёт по насыщенности,
    даже если его яркость формально низкая.
    """
    if not rgbs:
        return None
    avg_luma = sum(luminance(c) for c in rgbs) / len(rgbs)
    avg_sat = sum(saturation(c) for c in rgbs) / len(rgbs)
    return avg_luma <= DARK_MAX_LUMA and avg_sat <= MAX_SATURATION


def extract_fill(el):
    fill = (el.get("fill") or "").strip()
    style = el.get("style") or ""
    if fill:
        return fill
    m = re.search(r"(?:^|;)\s*fill\s*:\s*([^;]+)", style, re.I)
    return m.group(1).strip() if m else None


# --------------------------------------------------------------- gradients --

def find_gradient_by_id(root, gid):
    for el in root.iter():
        if el.get("id") == gid and tag_name(el) in {"linearGradient", "radialGradient"}:
            return el
    return None


def gradient_stops_colors(root, gradient, _seen=None):
    """RGB стопов градиента; разворачивает цепочки xlink:href (шаблонные градиенты)."""
    if _seen is None:
        _seen = set()
    gid = gradient.get("id")
    if gid in _seen:
        return []
    _seen.add(gid)

    colors = []
    for stop in gradient:
        if tag_name(stop) != "stop":
            continue
        c = stop.get("stop-color")
        if not c:
            style = stop.get("style") or ""
            sm = re.search(r"stop-color\s*:\s*([^;]+)", style, re.I)
            c = sm.group(1).strip() if sm else None
        rgb = parse_color(c)
        if rgb:
            colors.append(rgb)

    if not colors:
        href = gradient.get(f"{{{XLINK_NS}}}href") or gradient.get("href")
        if href and href.startswith("#"):
            parent = find_gradient_by_id(root, href[1:])
            if parent is not None:
                colors = gradient_stops_colors(root, parent, _seen)

    return colors


def gradient_is_dark(root, fill):
    m = re.fullmatch(r"url\(\s*#([^)]+)\s*\)", fill or "", re.I)
    if not m:
        return None

    gradient = find_gradient_by_id(root, m.group(1))
    if gradient is None:
        return None

    colors = gradient_stops_colors(root, gradient)
    return colors_are_dark_neutral(colors)


def fill_is_dark(root, el):
    fill = extract_fill(el)
    if not fill or fill.lower() == "none":
        return False

    rgb = parse_color(fill)
    if rgb:
        return bool(colors_are_dark_neutral([rgb]))

    gradient_dark = gradient_is_dark(root, fill)
    if gradient_dark is not None:
        return gradient_dark

    # Неизвестный формат заливки (например, class= со стилями в <style>)
    # -> НЕ считаем тёмным фоном (см. п.15 ТЗ: лучше пропустить файл,
    # чем случайно снести часть логотипа).
    return False


# ------------------------------------------------------------ raster <image> --

def decode_image_bytes(el, svg_path):
    href = el.get(f"{{{XLINK_NS}}}href") or el.get("href")
    if not href:
        return None
    href = href.strip()
    try:
        if href.startswith("data:"):
            m = re.match(r"data:image/[^;]+;base64,(.*)", href, re.S)
            if not m:
                return None
            return base64.b64decode(m.group(1))
        img_path = (svg_path.parent / href).resolve()
        if img_path.is_file():
            return img_path.read_bytes()
    except Exception:
        return None
    return None


def image_is_dark(el, svg_path):
    """
    Лучшее возможное определение тёмного растрового фона.
    Требует Pillow. Если Pillow нет или картинку не удалось декодировать —
    возвращаем None ("не уверены"), и такой <image> НИКОГДА не считается
    фоном (безопасный дефолт, п.15 ТЗ).
    """
    if not HAVE_PIL:
        return None
    data = decode_image_bytes(el, svg_path)
    if not data:
        return None
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = im.convert("RGB").resize((8, 8))
            pixels = list(im.getdata())
    except Exception:
        return None
    return colors_are_dark_neutral(pixels)


# ------------------------------------------------------------------ geometry --

def geometry_score(el, canvas=CANVAS_DEFAULT):
    t = tag_name(el)
    x = num(el.get("x")) or 0
    y = num(el.get("y")) or 0
    w = num(el.get("width"))
    h = num(el.get("height"))

    if t == "rect" and w is not None and h is not None:
        near_full = (
            w >= canvas * 0.75 and h >= canvas * 0.75
            and x <= canvas * 0.15 and y <= canvas * 0.15
        )
        rounded = num(el.get("rx")) is not None or num(el.get("ry")) is not None
        score = 0.98 if near_full else 0.0
        if rounded:
            score += 0.35
        return score

    if t == "image" and w is not None and h is not None:
        area = w * h
        if area >= canvas * canvas * 0.70 or (w >= canvas * 0.85 and h >= canvas * 0.85):
            return 0.90
        return 0.0

    if t == "path":
        d = el.get("d", "")
        if len(d) > 100:
            return 0.72

    return 0.0


def is_canvas_rect(el, canvas=CANVAS_DEFAULT):
    if tag_name(el) != "rect":
        return False
    w = num(el.get("width"))
    h = num(el.get("height"))
    x = num(el.get("x")) or 0
    y = num(el.get("y")) or 0
    return (
        w is not None and h is not None
        and w >= canvas * 0.98 and h >= canvas * 0.98
        and x <= 0.1 and y <= 0.1
    )


def find_background(root, svg_path):
    """
    Ищет РОВНО ОДИН тёмный фон. Геометрия сама по себе не решает:
    цветной (синий/жёлтый/...) скруглённый прямоугольник такого же
    размера НЕ будет выбран, потому что fill_is_dark() вернёт False.
    """
    candidates = []

    for index, el in enumerate(list(root)):
        t = tag_name(el)
        if t == "defs" or t not in GRAPHIC_TAGS:
            continue
        if is_canvas_rect(el) and extract_fill(el) in (None, "none"):
            continue

        score = geometry_score(el)
        if score < 0.65:
            continue

        if t == "image":
            dark = image_is_dark(el, svg_path)
            if dark is not True:
                continue  # нет уверенности -> не трогаем
        else:
            if not fill_is_dark(root, el):
                continue

        candidates.append((score, index, el))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def remove_transparent_canvas_helpers(root):
    for el in list(root):
        if is_canvas_rect(el):
            fill = extract_fill(el)
            if fill is None or fill.lower() == "none":
                root.remove(el)


# ---------------------------------------------------------------- ids/refs --

def rename_ids_and_refs(elements, prefix):
    mapping = {}
    for el in elements:
        for node in el.iter():
            old = node.get("id")
            if old:
                new = prefix + old
                mapping[old] = new
                node.set("id", new)

    if not mapping:
        return

    for el in elements:
        for node in el.iter():
            for key, value in list(node.attrib.items()):
                if not isinstance(value, str):
                    continue
                for old, new in mapping.items():
                    value = value.replace(f"url(#{old})", f"url(#{new})")
                    if value == f"#{old}":
                        value = f"#{new}"
                node.set(key, value)


# ----------------------------------------------------------------- template --

def template_nodes(template_root):
    return [copy.deepcopy(el) for el in list(template_root) if tag_name(el) != "defs"]


def template_defs(template_root):
    return [copy.deepcopy(el) for el in list(template_root) if tag_name(el) == "defs"]


# -------------------------------------------------------------------- core --

def analyze(src_path):
    """Парсит файл и ищет тёмный фон. Используется и в dry-run, и в реальном режиме."""
    tree = ET.parse(src_path)
    root = tree.getroot()
    bg = find_background(root, src_path)
    return tree, root, bg


def process(src_path, dst_path, tpl_root, copy_unchanged):
    """
    Возвращает 'processed' или 'skipped'.
    Если тёмный фон не найден — исходный файл НЕ модифицируется руками
    скрипта в принципе; в output либо кладётся байт-в-байт копия
    (copy_unchanged=True), либо ничего не пишется.
    """
    tree, root, bg = analyze(src_path)

    if bg is None:
        if copy_unchanged:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
        return "skipped"

    root.remove(bg)
    remove_transparent_canvas_helpers(root)

    defs = template_defs(tpl_root)
    nodes = template_nodes(tpl_root)
    rename_ids_and_refs(defs + nodes, "tpl_black_")

    src_defs = next((e for e in list(root) if tag_name(e) == "defs"), None)
    if defs:
        if src_defs is None:
            src_defs = ET.Element(f"{{{SVG_NS}}}defs")
            root.insert(0, src_defs)
        for d in defs:
            for child in list(d):
                src_defs.append(child)

    insert_at = 0
    for i, el in enumerate(list(root)):
        if tag_name(el) == "defs":
            insert_at = i + 1

    for node in reversed(nodes):
        root.insert(insert_at, node)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst_path, encoding="utf-8", xml_declaration=True)
    return "processed"


# -------------------------------------------------------------------- main --

def main():
    ap = argparse.ArgumentParser(
        description=(
            "Заменяет ТЁМНЫЙ фон app-иконок на app-template-black.svg. "
            "Цветные фоны не трогаются."
        )
    )
    ap.add_argument("input", type=Path, help="SVG-файл или директория")
    ap.add_argument("output", type=Path, help="выходной файл или директория")
    ap.add_argument("--template", type=Path, required=True,
                     help="путь к app-template-black.svg")
    ap.add_argument("--dry-run", action="store_true",
                     help="ничего не пишет, только показывает PROCESS/SKIP по каждому файлу")
    ap.add_argument("--verbose", action="store_true",
                     help="печатать каждый обработанный файл")
    ap.add_argument("--only-changed", action="store_true",
                     help="не копировать в output файлы без тёмного фона "
                          "(по умолчанию они копируются как есть, чтобы "
                          "output был полным зеркалом input)")
    args = ap.parse_args()

    if not args.template.is_file():
        print(
            f"[ERR] Шаблон не найден: {args.template}\n"
            "Проверьте путь командой:\n"
            "  find ~/Проекты/adw -type f -name 'app-template-black.svg'",
            file=sys.stderr,
        )
        return 2

    if not HAVE_PIL:
        print(
            "[WARN] Pillow не установлен - растровые <image>-фоны никогда "
            "не будут распознаны как тёмные (безопасный дефолт). "
            "Для их поддержки: pip install Pillow",
            file=sys.stderr,
        )

    tpl_tree = ET.parse(args.template)
    tpl_root = tpl_tree.getroot()
    copy_unchanged = not args.only_changed

    # --- одиночный файл -----------------------------------------------
    if args.input.is_file():
        out = args.output
        if out.is_dir():
            out = out / args.input.name

        try:
            if args.dry_run:
                _, _, bg = analyze(args.input)
                verdict = "PROCESS" if bg is not None else "SKIP"
                print(f"[{verdict}] {args.input} -> {out}")
            else:
                status = process(args.input, out, tpl_root, copy_unchanged)
                print(f"[{status.upper()}] {args.input} -> {out}")
        except Exception as e:
            print(f"[ERR] {args.input}: {e}", file=sys.stderr)
            return 1

        return 0

    if not args.input.is_dir():
        print(f"[ERR] Вход не найден: {args.input}", file=sys.stderr)
        return 2

    # --- директория ------------------------------------------------------
    files = list(args.input.rglob("*.svg"))
    print(f"Найдено SVG: {len(files)}")

    processed = 0
    skipped = 0
    errors = 0

    for src in files:
        rel = src.relative_to(args.input)
        dst = args.output / rel

        try:
            if args.dry_run:
                _, _, bg = analyze(src)
                if bg is not None:
                    processed += 1
                    if args.verbose:
                        print(f"[PROCESS] {src}")
                else:
                    skipped += 1
                    if args.verbose:
                        print(f"[SKIP]    {src}")
            else:
                status = process(src, dst, tpl_root, copy_unchanged)
                if status == "processed":
                    processed += 1
                    if args.verbose:
                        print(f"[OK]   {src}")
                else:
                    skipped += 1
                    if args.verbose:
                        print(f"[SKIP] {src}")
        except Exception as e:
            errors += 1
            print(f"[ERR] {src}: {e}")

    print()
    print(f"Найдено:     {len(files)}")
    print(f"{'Будет обработано' if args.dry_run else 'Обработано (фон заменён)'}: {processed}")
    print(f"{'Будет пропущено' if args.dry_run else 'Пропущено (тёмный фон не найден)'}: {skipped}")
    print(f"Ошибок:      {errors}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
