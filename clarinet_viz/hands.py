"""Shaded, semi-realistic hands seen from the back, reaching in from the left.

Each finger is built as a tapered tube along a gently arched centre line, with
joint bulges, knuckle creases and a nail. Drawing happens in passes (outline,
fill, details) so the palm and fingers read as one continuous shape. The same
geometry can be filled flat for the soft drop shadow.
"""

from __future__ import annotations

import math

import cairo

from . import layout as L
from .draw import set_rgb


def _catmull_rom(ctx: cairo.Context, pts, closed: bool = False, tension: float = 0.5) -> None:
    """Smooth path through points."""
    n = len(pts)
    if closed:
        ctx.move_to(*pts[0])
        rng = range(n)
    else:
        ctx.move_to(*pts[0])
        rng = range(n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        ctx.curve_to(*c1, *c2, *p2)
    if closed:
        ctx.close_path()


class Finger:
    """Geometry of one finger for a given knuckle and fingertip position."""

    SAMPLES = 22

    def __init__(self, base, tip, width: float, arch: float = 0.05, root_len: float = 0.55):
        dx, dy = tip[0] - base[0], tip[1] - base[1]
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        # Start a little inside the hand so the finger grows out of the palm.
        start = (base[0] - ux * width * root_len, base[1] - uy * width * root_len)
        self.width = width
        self.length = length
        self.u = (ux, uy)
        # Normal pointing "up" the screen relative to the finger: the lit side.
        self.n = (uy, -ux) if ux >= 0 else (-uy, ux)
        mid = ((start[0] + tip[0]) / 2, (start[1] + tip[1]) / 2)
        arch_px = arch * length
        self.ctrl = (mid[0] + self.n[0] * arch_px, mid[1] + self.n[1] * arch_px)
        self.start, self.tip = start, tip
        self.center, self.tangent, self.half = [], [], []
        for i in range(self.SAMPLES + 1):
            s = i / self.SAMPLES
            p, t = self._bez(s)
            self.center.append(p)
            self.tangent.append(t)
            self.half.append(self.profile(s) * width / 2)

    def _bez(self, s: float):
        a, c, b = self.start, self.ctrl, self.tip
        p = ((1 - s) ** 2 * a[0] + 2 * (1 - s) * s * c[0] + s * s * b[0],
             (1 - s) ** 2 * a[1] + 2 * (1 - s) * s * c[1] + s * s * b[1])
        tx = 2 * (1 - s) * (c[0] - a[0]) + 2 * s * (b[0] - c[0])
        ty = 2 * (1 - s) * (c[1] - a[1]) + 2 * s * (b[1] - c[1])
        ln = math.hypot(tx, ty) or 1.0
        return p, (tx / ln, ty / ln)

    @staticmethod
    def profile(s: float) -> float:
        """Width along the finger: tapering, with bulges at the two joints."""
        bump = lambda c, w: math.exp(-((s - c) / w) ** 2)
        return 1.0 - 0.2 * s + 0.05 * bump(0.52, 0.06) + 0.04 * bump(0.78, 0.05)

    def at(self, s: float):
        p, t = self._bez(s)
        return p, t, self.profile(s) * self.width / 2

    def path(self, ctx: cairo.Context, grow: float = 0.0) -> None:
        left, right = [], []
        for p, t, h in zip(self.center, self.tangent, self.half):
            nx, ny = -t[1], t[0]
            left.append((p[0] + nx * (h + grow), p[1] + ny * (h + grow)))
            right.append((p[0] - nx * (h + grow), p[1] - ny * (h + grow)))
        ctx.new_path()
        _catmull_rom(ctx, left)
        # Rounded fingertip: half circle from the left side round to the right.
        t = self.tangent[-1]
        ang = math.atan2(t[0], -t[1])  # angle of the left-hand normal
        cx, cy = self.center[-1]
        ctx.arc_negative(cx, cy, self.half[-1] + grow, ang, ang - math.pi)
        rr = list(reversed(right))
        ctx.line_to(*rr[0])
        for i in range(len(rr) - 1):
            ctx.line_to(*rr[i + 1])
        ctx.close_path()


def _palm_points(hand: dict, fingers: dict[str, Finger]):
    wx, wy = hand["wrist"]
    half = hand["wrist_half"]
    names = hand["fingers"]
    first, last = fingers[names[0]], fingers[names[-1]]
    k1, k4 = L.KNUCKLES[names[0]], L.KNUCKLES[names[-1]]
    pts = [(wx - 60, wy - half), (wx + 120, wy - half - 22)]
    pts.append((k1[0] - 70, k1[1] - first.width * 0.62))
    pts.append((k1[0] - 6, k1[1] - first.width * 0.5))
    for f in names:
        k = L.KNUCKLES[f]
        pts.append((k[0] + 6, k[1]))
    pts.append((k4[0] - 8, k4[1] + last.width * 0.5))
    pts.append((k4[0] - 80, k4[1] + last.width * 0.75))
    pts.append((wx + 120, wy + half + 18))
    pts.append((wx - 60, wy + half))
    return pts


def _sleeve(ctx: cairo.Context, hand: dict, mode: str) -> None:
    wx, wy = hand["wrist"]
    half = hand["wrist_half"] + 30
    ctx.new_path()
    ctx.move_to(-20, wy - half - 10)
    ctx.curve_to(wx + 30, wy - half - 14, wx + 64, wy - half + 10, wx + 70, wy - half + 30)
    ctx.curve_to(wx + 82, wy - 40, wx + 82, wy + 40, wx + 70, wy + half - 30)
    ctx.curve_to(wx + 64, wy + half - 10, wx + 30, wy + half + 14, -20, wy + half + 10)
    ctx.close_path()
    if mode == "silhouette":
        ctx.fill()
        return
    g = cairo.LinearGradient(0, wy - half, 0, wy + half)
    g.add_color_stop_rgb(0, *L.SLEEVE_LIGHT)
    g.add_color_stop_rgb(0.45, *L.SLEEVE)
    g.add_color_stop_rgb(1, *[c * 0.6 for c in L.SLEEVE])
    ctx.set_source(g)
    ctx.fill_preserve()
    set_rgb(ctx, L.INK, 0.8)
    ctx.set_line_width(2.5)
    ctx.stroke()
    # Fabric folds.
    ctx.set_line_width(2)
    set_rgb(ctx, (0, 0, 0), 0.25)
    for k in (-0.45, 0.1, 0.55):
        ctx.move_to(wx - 30, wy + k * half)
        ctx.curve_to(wx, wy + k * half - 8, wx + 30, wy + k * half + 6, wx + 60, wy + k * half - 2)
    ctx.stroke()


def _finger_fill(ctx: cairo.Context, f: Finger) -> None:
    p, _, h = f.at(0.5)
    nx, ny = f.n
    g = cairo.LinearGradient(p[0] + nx * h * 1.1, p[1] + ny * h * 1.1,
                             p[0] - nx * h * 1.1, p[1] - ny * h * 1.1)
    g.add_color_stop_rgb(0.0, *L.SKIN_LIGHT)
    g.add_color_stop_rgb(0.3, *L.SKIN_LIGHT)
    g.add_color_stop_rgb(0.55, *L.SKIN)
    g.add_color_stop_rgb(0.85, *L.SKIN_SHADE)
    g.add_color_stop_rgb(1.0, *L.SKIN_DEEP)
    f.path(ctx)
    ctx.set_source(g)
    ctx.fill()


def _finger_details(ctx: cairo.Context, f: Finger, pressed: float) -> None:
    w = f.width
    # Knuckle creases at the middle and end joints.
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for s, count, spread in ((0.52, 3, 0.55), (0.78, 2, 0.45)):
        p, t, h = f.at(s)
        nx, ny = -t[1], t[0]
        for i in range(count):
            off = (i - (count - 1) / 2) * 5.5
            cx, cy = p[0] + t[0] * off, p[1] + t[1] * off
            a = (cx + nx * h * spread, cy + ny * h * spread)
            b = (cx - nx * h * spread, cy - ny * h * spread)
            c = (cx + t[0] * 3.5, cy + t[1] * 3.5)
            ctx.move_to(*a)
            ctx.curve_to(c[0] + nx * h * 0.2, c[1] + ny * h * 0.2,
                         c[0] - nx * h * 0.2, c[1] - ny * h * 0.2, *b)
        set_rgb(ctx, L.SKIN_LINE, 0.42)
        ctx.set_line_width(1.7)
        ctx.stroke()
    # Soft highlight over each joint.
    for s in (0.52, 0.78):
        p, t, h = f.at(s)
        nx, ny = f.n
        hx, hy = p[0] + nx * h * 0.35, p[1] + ny * h * 0.35
        g = cairo.RadialGradient(hx, hy, 0, hx, hy, h * 0.9)
        g.add_color_stop_rgba(0, 1, 0.93, 0.86, 0.45)
        g.add_color_stop_rgba(1, 1, 0.93, 0.86, 0)
        ctx.set_source(g)
        ctx.arc(hx, hy, h * 0.9, 0, 2 * math.pi)
        ctx.fill()
    # Nail.
    p, t, h = f.at(0.9)
    ang = math.atan2(t[1], t[0])
    ctx.save()
    ctx.translate(*p)
    ctx.rotate(ang)
    nl, nw = w * 0.5, h * 1.2
    ctx.new_path()
    ctx.move_to(-nl / 2, -nw / 2)
    ctx.line_to(nl * 0.25, -nw / 2)
    ctx.curve_to(nl * 0.6, -nw / 2, nl * 0.62, nw / 2, nl * 0.25, nw / 2)
    ctx.line_to(-nl / 2, nw / 2)
    ctx.curve_to(-nl * 0.62, nw * 0.3, -nl * 0.62, -nw * 0.3, -nl / 2, -nw / 2)
    ctx.close_path()
    g = cairo.LinearGradient(0, -nw / 2, 0, nw / 2)
    g.add_color_stop_rgb(0, *[min(1, c * 1.06) for c in L.NAIL])
    g.add_color_stop_rgb(0.6, *L.NAIL)
    g.add_color_stop_rgb(1, *L.NAIL_SHADE)
    ctx.set_source(g)
    ctx.fill_preserve()
    set_rgb(ctx, L.SKIN_LINE, 0.6)
    ctx.set_line_width(1.4)
    ctx.stroke()
    # Free edge and shine.
    ctx.move_to(nl * 0.3, -nw * 0.42)
    ctx.curve_to(nl * 0.55, -nw * 0.3, nl * 0.55, nw * 0.3, nl * 0.3, nw * 0.42)
    set_rgb(ctx, (1, 1, 1), 0.55)
    ctx.set_line_width(2.2)
    ctx.stroke()
    ctx.move_to(-nl * 0.3, -nw * 0.22)
    ctx.line_to(nl * 0.1, -nw * 0.26)
    set_rgb(ctx, (1, 1, 1), 0.7)
    ctx.set_line_width(2.4)
    ctx.stroke()
    ctx.restore()


def build_fingers(tips: dict[str, tuple[tuple[float, float], float]], names) -> dict[str, Finger]:
    out = {}
    for f in names:
        tip, pressed = tips[f]
        out[f] = Finger(L.KNUCKLES[f], tip, L.FINGER_W[f], arch=0.03 + 0.04 * pressed)
    return out


def draw_hand(ctx: cairo.Context, hand_key: str, tips, mode: str = "full") -> None:
    """mode 'full' draws the shaded hand; 'silhouette' fills its shape with
    the current source (used for the shadow)."""
    hand = L.HANDS[hand_key]
    names = hand["fingers"]
    fingers = build_fingers(tips, names)
    palm = _palm_points(hand, fingers)

    if mode == "silhouette":
        ctx.new_path()
        _catmull_rom(ctx, palm, closed=True)
        ctx.fill()
        for f in fingers.values():
            f.path(ctx)
            ctx.fill()
        _sleeve(ctx, hand, mode)
        return

    # Pass 1: outlines of every part, so the union has a single contour.
    set_rgb(ctx, L.SKIN_LINE)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.new_path()
    _catmull_rom(ctx, palm, closed=True)
    ctx.set_line_width(5)
    ctx.stroke()
    for f in fingers.values():
        f.path(ctx)
        ctx.set_line_width(4.5)
        ctx.stroke()

    # Pass 2: palm fill.
    wx, wy = hand["wrist"]
    ys = [p[1] for p in palm]
    g = cairo.LinearGradient(0, min(ys), 0, max(ys))
    g.add_color_stop_rgb(0, *L.SKIN_LIGHT)
    g.add_color_stop_rgb(0.45, *L.SKIN)
    g.add_color_stop_rgb(1, *L.SKIN_SHADE)
    ctx.new_path()
    _catmull_rom(ctx, palm, closed=True)
    ctx.set_source(g)
    ctx.fill()

    # Pass 3: fingers, pinky first so the index sits on top.
    for name in reversed(names):
        _finger_fill(ctx, fingers[name])
    for name in names:
        _finger_details(ctx, fingers[name], tips[name][1])

    # Back-of-hand details: knuckle highlights and tendons.
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for name in names:
        k = L.KNUCKLES[name]
        g = cairo.RadialGradient(k[0] - 6, k[1] - 6, 0, k[0] - 6, k[1] - 6, 26)
        g.add_color_stop_rgba(0, 1, 0.95, 0.9, 0.55)
        g.add_color_stop_rgba(1, 1, 0.95, 0.9, 0)
        ctx.set_source(g)
        ctx.arc(k[0] - 6, k[1] - 6, 26, 0, 2 * math.pi)
        ctx.fill()
        ctx.move_to(k[0] - 30, k[1])
        ctx.curve_to(k[0] - 90, k[1] + (wy - k[1]) * 0.25, wx + 150, wy + (k[1] - wy) * 0.35,
                     wx + 100, wy + (k[1] - wy) * 0.25)
        set_rgb(ctx, L.SKIN_SHADE, 0.35)
        ctx.set_line_width(5)
        ctx.stroke()
    _sleeve(ctx, hand, mode)


def draw_thumb(ctx: cairo.Context, base, tip, pressed: float, mode: str = "full") -> None:
    """A thumb reaching behind the instrument (drawn before the body)."""
    f = Finger(base, tip, L.FINGER_W["LT"], arch=-0.06, root_len=0.2)
    if mode == "silhouette":
        f.path(ctx)
        ctx.fill()
        return
    f.path(ctx)
    set_rgb(ctx, L.SKIN_LINE)
    ctx.set_line_width(4.5)
    ctx.stroke()
    _finger_fill(ctx, f)
    _finger_details(ctx, f, pressed)
    # It sits in the shadow behind the clarinet.
    f.path(ctx)
    set_rgb(ctx, (0.1, 0.05, 0.05), 0.42)
    ctx.fill()
