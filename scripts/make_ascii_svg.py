"""Turn source-prepped.png into a self-typing ASCII portrait SVG.

Brightness is mapped onto a density ramp (sparse glyphs for bright pixels,
dense ones for dark pixels) and every row is revealed by a left-to-right clip
wipe, staggered top to bottom. The portrait prints once and freezes.

    python scripts/make_ascii_svg.py   # writes ascii-portrait.svg
"""

import argparse
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
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

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


def to_rows(
    img: Image.Image, cols: int, rows: int | None, gamma: float, contrast: float, crop: bool
) -> list[str]:
    gray = img.convert("L")
    if crop:
        gray = crop_to_subject(gray)
    gray = ImageEnhance.Contrast(ImageOps.autocontrast(gray, cutoff=(1, 2))).enhance(contrast)
    if rows is None:
        rows = max(1, round(gray.height / gray.width * cols * CW / LH))
    small = gray.resize((cols, rows), Image.LANCZOS)
    px = small.load()
    out = []
    for y in range(rows):
        line = []
        for x in range(cols):
            v = (px[x, y] / 255.0) ** gamma  # 0 dark .. 1 bright
            idx = min(len(RAMP) - 1, int((1.0 - v) * len(RAMP)))
            line.append(RAMP[idx])
        out.append("".join(line))
    return out


def build_svg(lines: list[str]) -> str:
    cols = len(lines[0])
    text_w = cols * CW
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
            f' textLength="{text_w:.1f}" lengthAdjust="spacing"'
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
    ap.add_argument("--cols", type=int, default=110)
    ap.add_argument("--rows", type=int, default=None, help="default: keep aspect")
    ap.add_argument("--gamma", type=float, default=1.0, help=">1 lightens, <1 darkens")
    ap.add_argument("--contrast", type=float, default=1.6)
    ap.add_argument("--no-crop", dest="crop", action="store_false", help="keep white margin")
    args = ap.parse_args()

    lines = to_rows(
        Image.open(args.src), args.cols, args.rows, args.gamma, args.contrast, args.crop
    )
    args.out.write_text(build_svg(lines), encoding="utf-8")
    print(f"wrote {args.out} ({args.cols}x{len(lines)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
