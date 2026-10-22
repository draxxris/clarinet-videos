"""Small cairo helpers for the inked comic look: thick black outlines,
flat cel shading, halftone dots and chunky lettering."""

from __future__ import annotations

import math
import subprocess
from functools import lru_cache

import cairo

from .layout import INK, WHITE


@lru_cache(maxsize=None)
def _installed_families() -> frozenset[str]:
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout
    except OSError:
        return frozenset()
    fams = set()
    for line in out.splitlines():
        fams.update(f.strip() for f in line.split(","))
    return frozenset(fams)


def pick_font(*families: str) -> str:
    fams = _installed_families()
    for f in families:
        if f in fams:
            return f
    return families[-1]


# Comic lettering font, best first. Bangers / Comic Neue look best if installed.
TITLE_FONT = None
TEXT_FONT = None
MUSIC_FONT = None


def fonts():
    global TITLE_FONT, TEXT_FONT, MUSIC_FONT
    if TITLE_FONT is None:
        TITLE_FONT = pick_font("Bangers", "Luckiest Guy", "Komika Axis", "Inter Display Black",
                               "Inter Display", "DejaVu Sans")
        TEXT_FONT = pick_font("Comic Neue", "Inter", "DejaVu Sans")
        MUSIC_FONT = pick_font("Bravura Text", "FreeSerif", "DejaVu Serif")
    return TITLE_FONT, TEXT_FONT, MUSIC_FONT


def set_rgb(ctx: cairo.Context, rgb, alpha: float = 1.0) -> None:
    ctx.set_source_rgba(rgb[0], rgb[1], rgb[2], alpha)


def mix(a, b, t: float):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def lighten(rgb, t: float):
    return mix(rgb, WHITE, t)


def darken(rgb, t: float):
    return mix(rgb, (0, 0, 0), t)


def rounded_rect(ctx: cairo.Context, x, y, w, h, r) -> None:
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def fill_ink(ctx: cairo.Context, fill, line_w: float = 5.0, alpha: float = 1.0) -> None:
    """Fill the current path, then outline it in ink."""
    set_rgb(ctx, fill, alpha)
    ctx.fill_preserve()
    set_rgb(ctx, INK, alpha)
    ctx.set_line_width(line_w)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.stroke()


def panel(ctx: cairo.Context, x, y, w, h, fill=WHITE, shadow: float = 9.0, line_w: float = 6.0) -> None:
    """A comic panel with a hard offset drop shadow."""
    rounded_rect(ctx, x + shadow, y + shadow, w, h, 10)
    set_rgb(ctx, INK)
    ctx.fill()
    rounded_rect(ctx, x, y, w, h, 10)
    fill_ink(ctx, fill, line_w)


def halftone(ctx: cairo.Context, x, y, w, h, color, spacing: float = 16, rmax: float = 4.2,
             cx=None, cy=None, falloff=None) -> None:
    """Ben-Day dots, shrinking with distance from (cx, cy)."""
    cx = x + w / 2 if cx is None else cx
    cy = y + h / 2 if cy is None else cy
    falloff = falloff or math.hypot(w, h) / 2
    set_rgb(ctx, color)
    row = 0
    yy = y
    while yy < y + h + spacing:
        xx = x + (spacing / 2 if row % 2 else 0)
        while xx < x + w + spacing:
            d = math.hypot(xx - cx, yy - cy) / falloff
            r = rmax * max(0.0, 1.0 - d) ** 0.8
            if r > 0.4:
                ctx.arc(xx, yy, r, 0, 2 * math.pi)
                ctx.fill()
            xx += spacing
        yy += spacing * 0.866
        row += 1


def text(ctx: cairo.Context, s: str, x, y, size, color=INK, font=None, bold=True,
         align="left", outline: float = 0.0, outline_color=INK, italic=False) -> float:
    """Draw text with its baseline at y. Returns the advance width."""
    family = font or fonts()[1]
    ctx.select_font_face(family,
                         cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    ext = ctx.text_extents(s)
    if align == "center":
        x -= ext.x_advance / 2
    elif align == "right":
        x -= ext.x_advance
    ctx.move_to(x, y)
    ctx.text_path(s)
    if outline > 0:
        set_rgb(ctx, outline_color)
        ctx.set_line_width(outline)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.stroke_preserve()
    set_rgb(ctx, color)
    ctx.fill()
    return ext.x_advance


def starburst(ctx: cairo.Context, cx, cy, r_out, r_in, points=14, rot=0.0, jitter=None) -> None:
    ctx.new_path()
    for i in range(points * 2):
        a = rot + math.pi * i / points
        r = r_out if i % 2 == 0 else r_in
        if jitter:
            r *= jitter[i % len(jitter)]
        ctx.line_to(cx + r * math.cos(a), cy + r * math.sin(a))
    ctx.close_path()


def capsule_stroke(ctx: cairo.Context, pts, width, fill, ink_w: float = 5.0, alpha: float = 1.0,
                   dash=None) -> None:
    """Stroke a polyline as a fat round-capped tube with an ink outline."""
    ctx.save()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.new_path()
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    set_rgb(ctx, INK, alpha)
    ctx.set_line_width(width + ink_w * 2)
    if dash:
        ctx.set_dash(dash)
    ctx.stroke_preserve()
    ctx.set_dash([])
    set_rgb(ctx, fill, alpha)
    ctx.set_line_width(width)
    ctx.stroke()
    ctx.restore()


def smoothstep(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)
