"""Render a neofetch-style info card SVG from data/profile.json.

Each line fades and slides in with staggered timing. Set STATIC=1 to emit a
frozen frame with no animation.

    python scripts/make_info_card.py          # writes info-card.svg
    STATIC=1 python scripts/make_info_card.py
"""

import argparse
import json
import os
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "data" / "profile.json"
OUT = ROOT / "info-card.svg"

BG = "#0d1117"
BAR = "#161b22"
BORDER = "#30363d"
KEY = "#39d353"
VAL = "#c9d1d9"
DIM = "#8b949e"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

FS = 12.5
CW = 7.5  # advance width at FS
LH = 22.0
PAD = 20.0
BAR_H = 30.0
WRAP = 46  # value characters per line
STAGGER = 0.09


def lines_for(cfg: dict) -> list[tuple[str, str]]:
    """Flatten rows into (key, value) pairs; wrapped continuations have an empty key."""
    out = []
    for row in cfg["rows"]:
        chunks = textwrap.wrap(row["value"], WRAP) or [""]
        out.append((row["key"], chunks[0]))
        out.extend(("", c) for c in chunks[1:])
    return out


def build_svg(cfg: dict, static: bool) -> str:
    title = cfg.get("title", cfg["username"])
    rows = lines_for(cfg)
    key_w = (max(len(k) for k, _ in rows) + 2) * CW

    w = PAD * 2 + key_w + WRAP * CW
    top = BAR_H + PAD
    h = top + (len(rows) + 2) * LH + PAD

    parts = []
    delay = 0.0

    def line(inner: str, y: float) -> str:
        # The row's position lives on the outer <g> as an attribute; the animation
        # lives on an inner <g>. A CSS transform would otherwise beat the attribute
        # and drop every row onto y=0.
        nonlocal delay
        d = "" if static else f' class="r" style="animation-delay:{delay:.2f}s"'
        delay += STAGGER
        return f'<g transform="translate(0 {y:.1f})"><g{d}>{inner}</g></g>'

    y = top
    parts.append(
        line(
            f'<text x="{PAD}" y="0" fill="{KEY}" font-weight="700">{escape(title)}</text>',
            y,
        )
    )
    y += LH
    parts.append(
        line(f'<text x="{PAD}" y="0" fill="{DIM}">{"-" * int(w / CW - 6)}</text>', y)
    )
    y += LH

    for key, val in rows:
        cells = ""
        if key:
            cells += f'<text x="{PAD}" y="0" fill="{KEY}">{escape(key)}</text>'
        cells += f'<text x="{PAD + key_w}" y="0" fill="{VAL}">{escape(val)}</text>'
        parts.append(line(cells, y))
        y += LH

    style = (
        ""
        if static
        else (
            "<style>"
            "@keyframes in{from{opacity:0;transform:translateX(-10px)}"
            "to{opacity:1;transform:translateX(0)}}"
            ".r{opacity:0;animation:in .45s cubic-bezier(.2,.8,.2,1) both}"
            "</style>"
        )
    )

    dots = "".join(
        f'<circle cx="{PAD + i * 18}" cy="{BAR_H / 2}" r="5" fill="{c}"/>'
        for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f"))
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}"'
        f' viewBox="0 0 {w:.0f} {h:.0f}" role="img" aria-label="{escape(title)} info card">'
        f"{style}"
        f'<rect width="100%" height="100%" rx="10" fill="{BG}" stroke="{BORDER}"/>'
        f'<path d="M0 10a10 10 0 0 1 10-10h{w - 20:.0f}a10 10 0 0 1 10 10v{BAR_H - 10:.0f}H0z" fill="{BAR}"/>'
        f'<line x1="0" y1="{BAR_H}" x2="{w:.0f}" y2="{BAR_H}" stroke="{BORDER}"/>'
        f"{dots}"
        f'<g font-family="{FONT}" font-size="{FS}" xml:space="preserve">{"".join(parts)}</g>'
        f"</svg>"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", type=Path, default=CFG)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    cfg = json.loads(args.cfg.read_text(encoding="utf-8"))
    static = os.environ.get("STATIC") == "1"
    args.out.write_text(build_svg(cfg, static), encoding="utf-8")
    print(f"wrote {args.out}{' (static)' if static else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
