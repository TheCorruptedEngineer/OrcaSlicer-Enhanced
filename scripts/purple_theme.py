#!/usr/bin/env python3
"""Apply the fork's purple accent theme (#B13CFF) to the source tree.

The theme is a colour-literal swap of Orca's accent teal, defined by the palette below (see FORK.md).
Running this after every upstream merge re-themes whatever teal upstream added, instead of
resolving the theme by hand in every conflict. It is idempotent: a themed tree comes out unchanged.

  python scripts/purple_theme.py              # rewrite the working tree in place
  python scripts/purple_theme.py --check      # list the files it would change, exit 1 if any
  python scripts/purple_theme.py --verify BASE THEMED
                                              # replay on git tree BASE and diff against THEMED: proves the
                                              # palette reproduces a hand-themed tree (residue = hand edits)

Files are read and written as bytes, so nothing but the matched ASCII literals can change (no mojibake).
PNGs are recoloured only when every visible pixel is one palette colour (a flat accent icon); that needs
Pillow, and without it PNGs are left alone with a warning.
"""
import argparse
import fnmatch
import io
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Where the theme lives: UI code, icons, web pages and the vendored ImGui.
SCOPE = ("src/", "resources/images/", "resources/web/", "deps_src/imgui/")
SUFFIXES = {".cpp", ".hpp", ".h", ".c", ".svg", ".html", ".htm", ".css", ".js", ".json", ".xml", ".png"}

# Teal that is print data or someone else's artwork, not our chrome.
EXCLUDE = (
    "src/libslic3r/PresetBundle.cpp",   # #26A69A is the default filament colour written into projects
    "src/slic3r/GUI/Plater.cpp",        # the filament swatch palette
    "resources/profiles/*",             # vendor bed textures
    "resources/flush/*",                # filament colour data
)

HEX = {
    # primary accent, and its off-by-one typos and brighter variants
    "009688": "B13CFF", "009789": "B13CFF", "009687": "B13CFF",
    "02c7b3": "B13CFF", "00f0d8": "B13CFF", "00ffea": "B13CFF", "00ffd9": "B13CFF",
    # hover (#52c7b8 is the icon hover tint BitmapCache swaps in for #00FF00)
    "26A69A": "C060FF", "4db6ac": "C060FF", "33aba1": "C060FF", "5eead4": "C060FF", "52c7b8": "C060FF",
    # pressed / dark
    "00877B": "8E2FBF", "00675b": "8E2FBF", "00897b": "8E2FBF", "00796B": "8E2FBF",
    # Button.cpp btn_confirm dark / light variants
    "22bfb0": "9B2FD9", "00FFD4": "D070FF",
    # hover in dark mode
    "008172": "9B4AE0",
    # accent at 10% / 25%
    "E5F0EE": "E5D6FF", "EBF9F0": "E5D6FF", "8de5d6": "E5D6FF",
    "BFE1DE": "BFDCFF",
    # dark-mode accent tints (#223C3C is the 25% one; the one 10% use is a hand edit)
    "223C3C": "3C2263", "244945": "3C2263", "283232": "322852",
}
# The same colours as integer triples: wxColour(0, 150, 136), rgba(0,150,136,.25), ImColor(...).
RGB = {
    (0, 150, 136): (177, 60, 255),
    (38, 166, 154): (192, 96, 255),
    (0, 137, 123): (142, 47, 191),
    (0, 129, 114): (155, 74, 224),
    (0, 122, 116): (142, 47, 191),   # CAD sketch banner background
    (0, 200, 180): (177, 60, 255),   # texture projector frame border
}
# Hex values a file must keep. StateColor's gDarkColors is a light->dark std::map built from an init-list,
# which keeps the FIRST entry for a key: turning its #EBF9F0 key into #E5D6FF would duplicate an existing
# key and silently drop one dark value. check_dark_map() guards the general case.
KEEP_HEX = {
    "src/slic3r/GUI/Widgets/StateColor.cpp": {"ebf9f0"},
}

_NUM = rb"\d+(?:\.\d*)?f?"            # 0, 0.0f, 150.f, 255.0
_DIV = rb"\s*/\s*255(?:\.\d*)?f?"     # " / 255.0f"


def _rules():
    rules = []
    lookup = {k.lower(): v for k, v in HEX.items()}
    # "#009688" and "0x009688", not part of a longer hex run. The replacement runs per file (see theme()).
    rules.append(("hex", re.compile(rb"(#|0x)(" + "|".join(HEX).encode() + rb")(?![0-9A-Fa-f])", re.I), lookup))
    # 0xAABBGGRR, as BitmapCache writes the accent for ImGui: 0xFF889600 is #009688.
    rules.append(("re", re.compile(rb"0x[Ff]{2}889600\b"), lambda m: b"0xFFFF3CB1"))
    for (r, g, b), (nr, ng, nb) in RGB.items():
        # Integer triple, any spacing.
        pat = rb"(?<![\d.])%d(\s*,\s*)%d(\s*,\s*)%d(?![\d.])" % (r, g, b)
        rules.append(("re", re.compile(pat),
                      lambda m, n=(nr, ng, nb): b"%d%s%d%s%d" % (n[0], m.group(1), n[1], m.group(2), n[2])))
        # Float triple over 255, any literal style: {0.0f, 150.f / 255.0f, 136.0f / 255} and the like.
        num = lambda v: rb"(?<![\d.])" + (b"%d" % v) + rb"(?:\.\d*)?f?"
        pat = num(r) + rb"(?:" + _DIV + rb")?\s*,\s*" + num(g) + _DIV + rb"\s*,\s*" + num(b) + _DIV
        rules.append(("re", re.compile(pat),
                      lambda m, n=(nr, ng, nb): b"%d.f / 255.f, %d.f / 255.f, %d.f / 255.f" % n))
    # ImGui accent as normalised floats
    rules.append(("re", re.compile(rb"ImVec4\(0, 0\.588, 0\.533, 1\)"), lambda m: b"ImVec4(0.694f, 0.235f, 1.0f, 1)"))
    # ImGui text selection highlight (0, 191, 191)
    rules.append(("re", re.compile(rb"ImVec4\(0, \.75f, \.75f,"), lambda m: b"ImVec4(177.f / 255.f, 60.f / 255.f, 255.f / 255.f,"))
    return rules


RULES = _rules()


def in_scope(path: str) -> bool:
    return (path.startswith(SCOPE) and Path(path).suffix.lower() in SUFFIXES
            and not any(fnmatch.fnmatch(path, pat) for pat in EXCLUDE))


_warned_no_pil = False


def theme_png(data: bytes) -> bytes:
    """Recolour a flat accent icon: every visible pixel one RGB from the palette. Anything else is artwork
    (logos, photos, gradients) and is returned untouched."""
    global _warned_no_pil
    try:
        from PIL import Image
    except ImportError:
        if not _warned_no_pil:
            print("warning: Pillow not installed, PNGs left unthemed", file=sys.stderr)
            _warned_no_pil = True
        return data
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return data          # not a readable PNG (one in resources/images isn't)
    if im.mode != "RGBA":
        return data
    pixels = im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()
    colours = {px[:3] for px in pixels if px[3] > 0}
    if len(colours) != 1 or next(iter(colours)) not in RGB:
        return data
    out = Image.new("RGBA", im.size, RGB[next(iter(colours))] + (0,))
    out.putalpha(im.getchannel("A"))
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def theme(data: bytes, path: str = "") -> bytes:
    if path.lower().endswith(".png"):
        return theme_png(data)
    keep = KEEP_HEX.get(path, set())
    for kind, rx, repl in RULES:
        if kind == "hex":
            data = rx.sub(lambda m: m.group(0) if m.group(2).decode().lower() in keep
                          else m.group(1) + repl[m.group(2).decode().lower()].encode(), data)
        else:
            data = rx.sub(repl, data)
    return data


def check_dark_map(data: bytes) -> list:
    """Keys that appear twice in StateColor's gDarkColors init-list (the later entry is silently dropped)."""
    block = re.search(rb"gDarkColors\s*\{(.*?)\n\};", data, re.S)
    if not block:
        return []
    keys = [k.upper() for k in re.findall(rb'\{\s*"(#[0-9A-Fa-f]{6})"\s*,', block.group(1))]
    return sorted({k.decode() for k in keys if keys.count(k) > 1})


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True).stdout.decode()


def tree_files(rev):
    return [p for p in git("ls-tree", "-r", "--name-only", rev).splitlines() if in_scope(p)]


def read_blobs(rev, paths):
    """{path: bytes} for `paths` at `rev`, through one `git cat-file --batch`."""
    proc = subprocess.run(["git", "cat-file", "--batch"], cwd=REPO, check=True, capture_output=True,
                          input="".join(f"{rev}:{p}\n" for p in paths).encode())
    out, pos, blobs = proc.stdout, 0, {}
    for p in paths:
        end = out.index(b"\n", pos)
        header = out[pos:end].split()
        pos = end + 1
        if header[-1] == b"missing":
            continue
        size = int(header[2])
        blobs[p] = out[pos:pos + size]
        pos += size + 1
    return blobs


def dark_map_problems(path: str, data: bytes) -> list:
    if not path.endswith("StateColor.cpp"):
        return []
    return [f"{path}: gDarkColors key {k} appears twice; the second entry is ignored" for k in check_dark_map(data)]


def run_in_place(check_only: bool) -> int:
    changed, problems = [], []
    for rel in git("ls-files").splitlines():
        if not in_scope(rel):
            continue
        path = REPO / rel
        data = path.read_bytes()
        new = theme(data, rel)
        problems += dark_map_problems(rel, new)
        if new != data:
            changed.append(rel)
            if not check_only:
                path.write_bytes(new)
    for rel in changed:
        print(rel)
    for p in problems:
        print("ERROR " + p, file=sys.stderr)
    print(f"{len(changed)} file(s) {'would change' if check_only else 'themed'}", file=sys.stderr)
    return 1 if problems or (check_only and changed) else 0


def verify(base: str, themed: str) -> int:
    """Replay on BASE and compare with THEMED. What differs is hand edits, or changes THEMED made besides the theme."""
    common = sorted(set(tree_files(base)) & set(tree_files(themed)))
    before, after = read_blobs(base, common), read_blobs(themed, common)
    residue = [rel for rel in common if rel in before and rel in after and theme(before[rel], rel) != after[rel]]
    print(f"{len(common) - len(residue)} files reproduced exactly, {len(residue)} differ (hand edits or other changes)")
    for rel in residue:
        print("  " + rel)
    return 0


def is_teal(r, g, b) -> bool:
    """Saturated blue-green, the hue family of Orca's accent (#009688 is 174 degrees)."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return 160 <= h * 360 <= 190 and s >= 0.35 and v >= 0.25


# Teal that is data, not chrome: colour pickers and swatches, G-code feature and preview colours, the
# terminal's ANSI palette, a vendor's own web page, tests. --scan skips these so it reports only new shades.
SCAN_IGNORE = (
    "src/libslic3r/*", "src/libvgcode/*",                  # print data and G-code viewer colours
    "deps_src/imgui/*",                                    # ImGui's own debug colours
    "resources/web/dialog/ColorPickerDialog/*", "resources/web/elegoolink/*", "resources/web/include/xterm/*",
    "resources/web/*/css/test.css", "resources/web/flush/WipingDialog.html",
    "src/slic3r/GUI/AMSMaterialsSetting.cpp",              # default filament colours
    "src/slic3r/GUI/ProgressStatusBar.cpp",                # {-1, 150, 155} are field widths
)
SCAN_IGNORE_COLOURS = {"#00FFFF", "(0, 255, 255)"}         # pure cyan: CMYW pigment, AMS test colours


def scan() -> int:
    """List teal-hued literals the palette does not cover - new upstream shades to map or to exempt."""
    found = {}
    hex_rx = re.compile(rb"#([0-9A-Fa-f]{6})(?![0-9A-Fa-f])")
    rgb_rx = re.compile(rb"(?<![\d.])(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?![\d.])")
    for rel in git("ls-files").splitlines():
        if (not in_scope(rel) or rel.lower().endswith(".png")
                or any(fnmatch.fnmatch(rel, pat) for pat in SCAN_IGNORE)):
            continue
        data = (REPO / rel).read_bytes()
        for m in hex_rx.finditer(data):
            v = m.group(1).decode()
            if is_teal(int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)):
                found.setdefault("#" + v.upper(), set()).add(rel)
        if rel.endswith((".cpp", ".hpp", ".h", ".css", ".js", ".html")):
            for m in rgb_rx.finditer(data):
                r, g, b = (int(x) for x in m.groups())
                if max(r, g, b) <= 255 and is_teal(r, g, b):
                    found.setdefault(f"({r}, {g}, {b})", set()).add(rel)
    found = {c: f for c, f in found.items() if c not in SCAN_IGNORE_COLOURS}
    for colour, files in sorted(found.items(), key=lambda kv: -len(kv[1])):
        print(f"{colour:16s} {len(files):3d} file(s): {', '.join(sorted(files)[:4])}{' ...' if len(files) > 4 else ''}")
    print(f"{len(found)} teal-hued literal(s) left", file=sys.stderr)
    return 1 if found else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--scan", action="store_true", help="list teal-hued literals the palette leaves behind")
    ap.add_argument("--verify", nargs=2, metavar=("BASE", "THEMED"))
    a = ap.parse_args()
    if a.verify:
        return verify(*a.verify)
    if a.scan:
        return scan()
    return run_in_place(a.check)


if __name__ == "__main__":
    sys.exit(main())
