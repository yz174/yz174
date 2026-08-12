"""Turn source-prepped.png into a self-typing ASCII portrait SVG.

Brightness is mapped onto a density ramp (sparse glyphs for bright pixels,
dense ones for dark pixels) and every row is revealed by a left-to-right clip
wipe, staggered top to bottom. The portrait prints once and freezes.

    python scripts/make_ascii_svg.py             # from source-prepped.png
    python scripts/make_ascii_svg.py --text a.txt  # from ready-made art

--text skips image conversion and animates an existing character grid, which is
how Braille art (U+2800) gets in: a Braille cell packs a 2x4 dot matrix, so it
resolves eight sub-pixels per character and a one-glyph-per-pixel ramp cannot
reproduce it.
"""

import argparse
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-prepped.png"
OUT = ROOT / "ascii-portrait.svg"

RAMP = " .`:-=+*cs#%@"  # bright (sparse) -> dark (dense)

BG = "#0d1117"
FG = "#c9d1d9"
BORDER = "#30363d"
# 'DejaVu Sans Mono' and 'Segoe UI Symbol' are here for Braille (U+2800) coverage;
# the leading families have none, so browsers fall back per glyph.
FONT = (
    "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',"
    "'Segoe UI Symbol','Liberation Mono',monospace"
)

FS = 10.0  # font size
CW = 6.0  # monospace advance width at FS
LH = 10.2  # line height
PAD = 14.0

STAGGER = 0.028  # seconds between consecutive rows
WIPE = 0.42  # seconds for one row to wipe in


def crop_to_subject(gray: Image.Image, pad_frac: float = 0.02) -> Image.Image:
    """Trim the white margin left by the cutout so the face fills the grid."""
    box = gray.point(lambda v: 255 if v < 245 else 0).getbbox()
    if not box:
        return gray
    mx, my = gray.width * pad_frac, gray.height * pad_frac
    return gray.crop(
        (
            max(0, int(box[0] - mx)),
            max(0, int(box[1] - my)),
            min(gray.width, int(box[2] + mx)),
            min(gray.height, int(box[3] + my)),
        )
    )


def edge_grid(gray: Image.Image, cols: int, rows: int) -> "list[list[bool]]":
    """Which character cells contain an outline. Flat art carries its shape here,
    not in its tone, so a photo-style brightness ramp alone renders it as mush.

    Detection happens at grid resolution, not full resolution. A hand-drawn outline
    is several pixels thick, so full-res Canny traces both of its sides; pooling those
    parallel edges onto a coarse grid fuses them into a blob. Downscaling first makes
    the outline one pixel wide, which yields the one-character-wide line we want.
    """
    import cv2
    import numpy as np

    small = gray.resize((cols, rows), Image.LANCZOS)
    return (cv2.Canny(np.asarray(small), 40, 120) > 0).tolist()


def to_rows(
    img: Image.Image,
    cols: int,
    rows: int | None,
    gamma: float,
    contrast: float,
    crop: bool,
    edges: bool = False,
    fill_max: int = 2,
    fill_min: int = 0,
    invert: bool = False,
) -> list[str]:
    gray = img.convert("L")
    if crop:
        gray = crop_to_subject(gray)
    gray = ImageEnhance.Contrast(ImageOps.autocontrast(gray, cutoff=(1, 2))).enhance(contrast)
    if rows is None:
        rows = max(1, round(gray.height / gray.width * cols * CW / LH))
    egrid = edge_grid(gray, cols, rows) if edges else None
    top = fill_max if edges else len(RAMP) - 1
    small = gray.resize((cols, rows), Image.LANCZOS)
    px = small.load()
    out = []
    for y in range(rows):
        line = []
        for x in range(cols):
            if egrid and egrid[y][x]:
                idx = len(RAMP) - 1
            else:
                v = (px[x, y] / 255.0) ** gamma  # 0 dark .. 1 bright
                idx = max(fill_min, min(top, int((1.0 - v) * (top + 1))))
            if invert:
                idx = len(RAMP) - 1 - idx
            line.append(RAMP[idx])
        out.append("".join(line))
    return out


def build_svg(lines: list[str], adjust: str = "spacing", cw: float = CW) -> str:
    cols = max(len(line) for line in lines)
    text_w = cols * cw
    w = text_w + 2 * PAD
    h = len(lines) * LH + 2 * PAD

    clips, body = [], []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        y = PAD + i * LH
        begin = round(i * STAGGER, 3)
        clips.append(
            f'<clipPath id="w{i}"><rect x="{PAD}" y="{y:.1f}" height="{LH:.1f}" width="0">'
            f'<animate attributeName="width" values="0;{text_w:.1f}" keyTimes="0;1"'
            f' calcMode="spline" keySplines="0.2 0.8 0.2 1"'
            f' begin="{begin}s" dur="{WIPE}s" fill="freeze"/>'
            f"</rect></clipPath>"
        )
        body.append(
            f'<text clip-path="url(#w{i})" x="{PAD}" y="{y + FS * 0.78:.1f}"'
            f' textLength="{text_w:.1f}" lengthAdjust="{adjust}"'
            f' xml:space="preserve">{escape(line)}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}"'
        f' viewBox="0 0 {w:.0f} {h:.0f}" role="img" aria-label="ASCII portrait">'
        f'<rect x="0.5" y="0.5" width="{w - 1:.0f}" height="{h - 1:.0f}" rx="10"'
        f' fill="{BG}" stroke="{BORDER}"/>'
        f"<defs>{''.join(clips)}</defs>"
        f'<g font-family="{FONT}" font-size="{FS}" fill="{FG}">{"".join(body)}</g>'
        f"</svg>"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument(
        "--text",
        type=Path,
        help="animate this character grid verbatim instead of converting an image",
    )
    ap.add_argument("--cols", type=int, default=110)
    ap.add_argument("--rows", type=int, default=None, help="default: keep aspect")
    ap.add_argument("--gamma", type=float, default=1.0, help="<1 lightens, >1 darkens")
    ap.add_argument("--contrast", type=float, default=1.6)
    ap.add_argument("--no-crop", dest="crop", action="store_false", help="keep white margin")
    ap.add_argument(
        "--edges",
        action="store_true",
        help="outline mode for flat/cartoon art: Canny edges become the densest glyph",
    )
    ap.add_argument("--fill-max", type=int, default=2, help="--edges: max density for flat fills")
    ap.add_argument(
        "--fill-min",
        type=int,
        default=0,
        help="floor for flat fills; 1 tiles the whole canvas with dots instead of blanks",
    )
    ap.add_argument(
        "--invert", action="store_true", help="flip the ramp: dense where it was sparse"
    )
    ap.add_argument(
        "--cw",
        type=float,
        default=None,
        help=f"glyph advance width; default {CW} for ASCII, 7.5 for --text (Braille is wider)",
    )
    args = ap.parse_args()

    if args.text:
        lines = args.text.read_text(encoding="utf-8").splitlines()
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            print(f"{args.text} has no rows", file=sys.stderr)
            return 1
        cols = max(len(line) for line in lines)
        lines = [line.ljust(cols) for line in lines]
        # Braille blocks must stay flush; adjusting the gaps between them tears seams.
        adjust = "spacingAndGlyphs"
        cw = args.cw if args.cw else 7.5
    else:
        lines = to_rows(
            Image.open(args.src),
            args.cols,
            args.rows,
            args.gamma,
            args.contrast,
            args.crop,
            args.edges,
            args.fill_max,
            args.fill_min,
            args.invert,
        )
        cols, adjust = args.cols, "spacing"
        cw = args.cw if args.cw else CW

    args.out.write_text(build_svg(lines, adjust, cw), encoding="utf-8")
    print(f"wrote {args.out} ({cols}x{len(lines)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
