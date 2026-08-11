"""Render data/contributions.json as an animated contribution heatmap SVG.

53 weeks x 7 days of rounded boxes in a GitHub-ish palette. Boxes slide in
diagonally (top-left to bottom-right), play once and freeze. Includes the
Less -> More legend and a stats footer.

    python scripts/render_heatmap_svg.py   # writes contrib-heatmap.svg
"""

import argparse
import json
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "contributions.json"
OUT = ROOT / "contrib-heatmap.svg"

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

BG = "#0d1117"
BORDER = "#30363d"
DIM = "#8b949e"
FG = "#c9d1d9"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

CELL, GAP = 12.0, 3.0
PITCH = CELL + GAP
PAD = 16.0
LABEL_W = 30.0  # weekday gutter
MONTH_H = 20.0
FS = 10.0

STEP = 0.012  # seconds per diagonal step
POP = 0.36

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def sunday_index(d: date) -> int:
    """Weekday with Sunday = 0, matching GitHub's calendar rows."""
    return (d.weekday() + 1) % 7


def place(days: list[dict]) -> tuple[dict[tuple[int, int], dict], int]:
    """Map each day onto (column, row); columns are weeks starting on Sunday."""
    first = date.fromisoformat(days[0]["date"])
    origin = first.toordinal() - sunday_index(first)
    grid, cols = {}, 0
    for d in days:
        cur = date.fromisoformat(d["date"])
        col = (cur.toordinal() - origin) // 7
        grid[(col, sunday_index(cur))] = d
        cols = max(cols, col + 1)
    return grid, cols


def bright_threshold(days: list[dict]) -> int:
    """Counts at or above this get the brightest palette slot."""
    hot = sorted(d["count"] for d in days if d["level"] >= 4)
    if not hot:
        return 1 << 30
    return hot[int(len(hot) * 0.9)] if len(hot) > 1 else hot[0]


def build_svg(payload: dict) -> str:
    days = payload["days"]
    st = payload["stats"]
    grid, cols = place(days)
    hot = bright_threshold(days)

    gx, gy = PAD + LABEL_W, PAD + MONTH_H
    grid_w = cols * PITCH - GAP
    grid_h = 7 * PITCH - GAP
    w = gx + grid_w + PAD
    footer_y = gy + grid_h + 26
    h = footer_y + 34

    cells = []
    for (col, row), d in sorted(grid.items()):
        lvl = d["level"]
        color = PALETTE[5] if lvl >= 4 and d["count"] >= hot else PALETTE[min(lvl, 4)]
        delay = (col + row) * STEP
        cells.append(
            f'<rect class="d" x="{gx + col * PITCH:.1f}" y="{gy + row * PITCH:.1f}"'
            f' width="{CELL}" height="{CELL}" rx="2.5" fill="{color}"'
            f' style="animation-delay:{delay:.2f}s">'
            f'<title>{d["count"]} on {d["date"]}</title></rect>'
        )

    month_labels = []
    seen = set()
    for col in range(cols):
        d = grid.get((col, 0)) or next(
            (grid[(col, r)] for r in range(7) if (col, r) in grid), None
        )
        if not d:
            continue
        cur = date.fromisoformat(d["date"])
        if cur.month not in seen and cur.day <= 8:
            seen.add(cur.month)
            month_labels.append(
                f'<text x="{gx + col * PITCH:.1f}" y="{gy - 7:.1f}" fill="{DIM}">'
                f"{MONTHS[cur.month - 1]}</text>"
            )

    day_labels = "".join(
        f'<text x="{PAD}" y="{gy + r * PITCH + CELL - 2:.1f}" fill="{DIM}">{name}</text>'
        for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )

    legend_x = w - PAD - (len(PALETTE) * PITCH + 74)
    legend = [f'<text x="{legend_x:.1f}" y="{footer_y + 10:.1f}" fill="{DIM}">Less</text>']
    for i, c in enumerate(PALETTE):
        legend.append(
            f'<rect x="{legend_x + 32 + i * PITCH:.1f}" y="{footer_y:.1f}"'
            f' width="{CELL}" height="{CELL}" rx="2.5" fill="{c}"/>'
        )
    legend.append(
        f'<text x="{legend_x + 38 + len(PALETTE) * PITCH:.1f}" y="{footer_y + 10:.1f}"'
        f' fill="{DIM}">More</text>'
    )

    summary = (
        f'{st["total"]:,} contributions   '
        f'streak {st["current_streak"]}d (best {st["longest_streak"]}d)   '
        f'peak {st["best_day"]["count"]} on {st["best_day"]["date"]}'
    )

    style = (
        "<style>"
        "@keyframes pop{from{opacity:0;transform:translateY(-6px)}"
        "to{opacity:1;transform:translateY(0)}}"
        f"rect.d{{opacity:0;animation:pop {POP}s cubic-bezier(.2,.8,.2,1) both}}"
        "</style>"
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}"'
        f' viewBox="0 0 {w:.0f} {h:.0f}" role="img"'
        f' aria-label="{escape(payload["username"])} contribution heatmap">'
        f"{style}"
        f'<rect width="100%" height="100%" rx="10" fill="{BG}" stroke="{BORDER}"/>'
        f'<g font-family="{FONT}" font-size="{FS}">{"".join(month_labels)}{day_labels}'
        f'<text x="{PAD}" y="{footer_y + 10:.1f}" fill="{FG}">{escape(summary)}</text>'
        f'{"".join(legend)}</g>'
        f'<g>{"".join(cells)}</g>'
        f"</svg>"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    payload = json.loads(args.src.read_text(encoding="utf-8"))
    args.out.write_text(build_svg(payload), encoding="utf-8")
    print(f"wrote {args.out} - {len(payload['days'])} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
