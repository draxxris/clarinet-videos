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
from . import rig
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


def _wrist_fade(hand: dict) -> cairo.LinearGradient:
    """Alpha mask that fades the hand out toward the wrist, like a vignette."""
    wx, _ = hand["wrist"]
    g = cairo.LinearGradient(wx + 30, 0, wx + 210, 0)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(0.75, 0, 0, 0, 0.92)
    g.add_color_stop_rgba(1, 0, 0, 0, 1)
    return g


def _finger_fill(ctx: cairo.Context, f: Finger) -> None:
    p, _, h = f.at(0.5)
    nx, ny = f.n
    g = cairo.LinearGradient(p[0] + nx * h, p[1] + ny * h, p[0] - nx * h, p[1] - ny * h)
    g.add_color_stop_rgb(0.0, *L.SKIN_LIGHT)
    g.add_color_stop_rgb(0.45, *L.SKIN)
    g.add_color_stop_rgb(0.82, *L.SKIN)
    g.add_color_stop_rgb(1.0, *L.SKIN_SHADE)
    f.path(ctx)
    ctx.set_source(g)
    ctx.fill()


def _crease(ctx: cairo.Context, f: Finger, s: float, spread: float) -> None:
    """One small curved line across the finger, bowed toward the tip."""
    p, t, h = f.at(s)
    nx, ny = -t[1], t[0]
    a = (p[0] + nx * h * spread, p[1] + ny * h * spread)
    b = (p[0] - nx * h * spread, p[1] - ny * h * spread)
    bow = h * 0.35
    ctx.move_to(*a)
    ctx.curve_to(a[0] + t[0] * bow, a[1] + t[1] * bow, b[0] + t[0] * bow, b[1] + t[1] * bow, *b)


def _finger_details(ctx: cairo.Context, f: Finger, pressed: float) -> None:
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    # Joint creases, drawn as short ink strokes.
    _crease(ctx, f, 0.5, 0.3)
    _crease(ctx, f, 0.77, 0.22)
    set_rgb(ctx, L.SKIN_LINE, 0.5)
    ctx.set_line_width(2)
    ctx.stroke()
    # Nail: a U-shaped line following the fingertip, open toward the hand.
    t = f.tangent[-1]
    cx, cy = f.center[-1]
    h = f.half[-1]
    r = h * 0.62
    cx, cy = cx - t[0] * h * 0.12, cy - t[1] * h * 0.12
    ang = math.atan2(t[0], -t[1])
    leg = f.width * 0.32
    nxl, nyl = math.cos(ang), math.sin(ang)
    ctx.new_path()
    ctx.move_to(cx + nxl * r - t[0] * leg, cy + nyl * r - t[1] * leg)
    ctx.line_to(cx + nxl * r, cy + nyl * r)
    ctx.arc_negative(cx, cy, r, ang, ang - math.pi)
    ctx.line_to(cx - nxl * r - t[0] * leg, cy - nyl * r - t[1] * leg)
    ctx.curve_to(cx - t[0] * leg * 1.25 - nxl * r * 0.4, cy - t[1] * leg * 1.25 - nyl * r * 0.4,
                 cx - t[0] * leg * 1.25 + nxl * r * 0.4, cy - t[1] * leg * 1.25 + nyl * r * 0.4,
                 cx + nxl * r - t[0] * leg, cy + nyl * r - t[1] * leg)
    set_rgb(ctx, L.NAIL, 0.55)
    ctx.fill_preserve()
    set_rgb(ctx, L.SKIN_LINE, 0.85)
    ctx.set_line_width(2)
    ctx.stroke()


def build_fingers(tips: dict[str, tuple[tuple[float, float], float]], names) -> dict[str, Finger]:
    out = {}
    for f in names:
        tip, pressed = tips[f]
        out[f] = Finger(L.KNUCKLES[f], tip, L.FINGER_W[f], arch=0.03 + 0.04 * pressed)
    return out


def draw_hand(ctx: cairo.Context, hand_key: str, tips, pose: "rig.Pose", mode: str = "full") -> None:
    """mode 'full' draws the inked, shaded hand; 'silhouette' fills its shape
    with the current source (used for the shadow). Either way the hand fades
    out toward the wrist."""
    hand = L.HANDS[hand_key]
    names = hand["fingers"]
    # Build the hand in its rest-pose frame, then let the ctx transform place it.
    local = {f: (rig.to_local(hand_key, pose, tips[f][0]), tips[f][1]) for f in names}
    ctx.save()
    rig.apply(ctx, hand_key, pose)
    _draw_hand_local(ctx, hand, local, mode)
    ctx.restore()


def _draw_hand_local(ctx: cairo.Context, hand: dict, tips, mode: str) -> None:
    names = hand["fingers"]
    fingers = build_fingers(tips, names)
    palm = _palm_points(hand, fingers)
    fade = _wrist_fade(hand)

    if mode == "silhouette":
        src = ctx.get_source()
        ctx.push_group()
        ctx.set_source(src)
        ctx.new_path()
        _catmull_rom(ctx, palm, closed=True)
        ctx.fill()
        for f in fingers.values():
            f.path(ctx)
            ctx.fill()
        ctx.pop_group_to_source()
        ctx.mask(fade)
        return

    ctx.push_group()
    # Pass 1: outlines of every part, so the union has a single contour.
    set_rgb(ctx, L.SKIN_LINE)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.new_path()
    _catmull_rom(ctx, palm, closed=True)
    ctx.set_line_width(5)
    ctx.stroke()
    for f in fingers.values():
        f.path(ctx)
        ctx.set_line_width(5)
        ctx.stroke()

    # Pass 2: palm fill, lit from above with a soft shade along the bottom.
    ys = [p[1] for p in palm]
    g = cairo.LinearGradient(0, min(ys), 0, max(ys))
    g.add_color_stop_rgb(0, *L.SKIN_LIGHT)
    g.add_color_stop_rgb(0.5, *L.SKIN)
    g.add_color_stop_rgb(0.85, *L.SKIN)
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

    # Knuckle marks on the back of the hand.
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for name in names:
        f = fingers[name]
        k = L.KNUCKLES[name]
        ux, uy = f.u
        nx, ny = -uy, ux
        c = (k[0] - ux * 26, k[1] - uy * 26)
        h = f.width * 0.18
        ctx.move_to(c[0] + nx * h, c[1] + ny * h)
        ctx.curve_to(c[0] + nx * h - ux * 8, c[1] + ny * h - uy * 8,
                     c[0] - nx * h - ux * 8, c[1] - ny * h - uy * 8, c[0] - nx * h, c[1] - ny * h)
    set_rgb(ctx, L.SKIN_LINE, 0.35)
    ctx.set_line_width(2)
    ctx.stroke()
    ctx.pop_group_to_source()
    ctx.mask(fade)


def draw_thumb(ctx: cairo.Context, base, tip, pressed: float, mode: str = "full") -> None:
    """A thumb reaching behind the instrument (drawn before the body)."""
    f = Finger(base, tip, L.FINGER_W["LT"], arch=-0.06, root_len=0.2)
    if mode == "silhouette":
        f.path(ctx)
        ctx.fill()
        return
    f.path(ctx)
    set_rgb(ctx, L.SKIN_LINE)
    ctx.set_line_width(5)
    ctx.stroke()
    _finger_fill(ctx, f)
    _finger_details(ctx, f, pressed)
    # It sits in the shadow behind the clarinet.
    f.path(ctx)
    set_rgb(ctx, (0.05, 0.04, 0.08), 0.2)
    ctx.fill()
