"""Prepare a source photo for ASCII conversion.

Removes the background (rembg), boosts local contrast (CLAHE), composites onto
pure white and writes a grayscale source-prepped.png next to the repo root.

    python scripts/prep_photo.py source-photo.jpg

rembg is optional: if it is not installed, pass --no-rembg (or let the script
fall back automatically) and the whole frame is kept.
"""

import argparse
import io
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "source-prepped.png"


def cutout(img: Image.Image) -> Image.Image:
    """Return an RGBA image with the background removed, or None if unavailable."""
    try:
        from rembg import remove
    except ImportError:
        return None
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Image.open(io.BytesIO(remove(buf.getvalue()))).convert("RGBA")


def on_white(img: Image.Image) -> Image.Image:
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    white.alpha_composite(img)
    return white.convert("L")


def clahe(gray: Image.Image, clip: float, tiles: int) -> Image.Image:
    arr = np.asarray(gray)
    op = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tiles, tiles))
    return Image.fromarray(op.apply(arr))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("photo", type=Path)
    ap.add_argument("--no-rembg", action="store_true", help="skip background removal")
    ap.add_argument("--clip", type=float, default=2.5, help="CLAHE clip limit")
    ap.add_argument("--tiles", type=int, default=8, help="CLAHE tile grid size")
    ap.add_argument("--width", type=int, default=900, help="working width in px")
    args = ap.parse_args()

    if not args.photo.exists():
        print(f"no such file: {args.photo}", file=sys.stderr)
        return 1

    img = Image.open(args.photo).convert("RGBA")
    if img.width > args.width:
        h = round(img.height * args.width / img.width)
        img = img.resize((args.width, h), Image.LANCZOS)

    if not args.no_rembg:
        cut = cutout(img)
        if cut is None:
            print("rembg unavailable - keeping the full frame", file=sys.stderr)
        else:
            img = cut

    gray = clahe(on_white(img), args.clip, args.tiles)
    gray.save(OUT)
    print(f"wrote {OUT} ({gray.width}x{gray.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
