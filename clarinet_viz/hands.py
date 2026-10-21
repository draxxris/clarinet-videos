"""Inked, softly shaded hands seen from above (the player's view).

Each hand is drawn in its own frame, reaching in from the left; the rig
(rig.py) places it, mirroring the right hand so it comes in from the other
side of the instrument.

A finger is three phalanges of fixed length. When a fingertip is closer to
the knuckle than the finger is long, the finger is curled (or lifted toward
the viewer), so the segments are foreshortened, the outer ones most. The
outline has bulges at the joints and the fingertip pad, the palm fills the
webbing between finger bases, and drawing goes in passes (outline, fill,
details) so the whole hand reads as one shape.
"""

from __future__ import annotations

import math

import cairo

from . import layout as L
from . import rig
from .draw import set_rgb

SEGMENTS = (0.45, 0.31, 0.24)      # phalanx lengths as a share of the finger
SEG_FLEX = (0.35, 1.0, 1.7)        # how much each joint bends as the finger curls
MAX_CURL = 1.4


def _catmull_rom(ctx: cairo.Context, pts, closed: bool = False, tension: float = 0.5) -> None:
    """Smooth path through points (continues the current path if open)."""
    n = len(pts)
    if closed or not ctx.has_current_point():
        ctx.move_to(*pts[0])
    else:
        ctx.line_to(*pts[0])
    for i in range(n if closed else n - 1):
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        ctx.curve_to(*c1, *c2, *p2)
    if closed:
        ctx.close_path()


def _lerp(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def _unit(dx, dy):
    ln = math.hypot(dx, dy) or 1.0
    return dx / ln, dy / ln


class Finger:
    """Joint positions and outline of one finger for a knuckle and fingertip."""

    def __init__(self, base, tip, width: float, length: float, bow: float = 1.0,
                 root: float = 0.7):
        d = min(math.hypot(tip[0] - base[0], tip[1] - base[1]), length * 0.999)
        segs = [s * length for s in SEGMENTS]

        def projected(phi):
            return sum(l * max(math.cos(k * phi), 0.12) for l, k in zip(segs, SEG_FLEX))

        lo, hi = 0.0, MAX_CURL
        if projected(0) > d:
            for _ in range(30):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if projected(mid) > d else (lo, mid)
        phi = lo
        self.curl = phi / MAX_CURL
        proj = [l * max(math.cos(k * phi), 0.12) for l, k in zip(segs, SEG_FLEX)]
        # A curled finger is raised toward the viewer, so it reads a touch wider.
        self.w = width * (1 + 0.07 * self.curl)

        # Chain in a local frame, slightly bowed, then fitted onto base -> tip.
        angs = (0.06 * bow, 0.0, -0.05 * bow)
        pts = [(0.0, 0.0)]
        for l, a in zip(proj, angs):
            x, y = pts[-1]
            pts.append((x + l * math.cos(a), y + l * math.sin(a)))
        ex, ey = pts[-1]
        rot = math.atan2(tip[1] - base[1], tip[0] - base[0]) - math.atan2(ey, ex)
        sc = d / (math.hypot(ex, ey) or 1.0)
        c, s = math.cos(rot) * sc, math.sin(rot) * sc
        self.K, self.J1, self.J2, self.T = [
            (base[0] + c * x - s * y, base[1] + s * x + c * y) for x, y in pts]
        self.u = _unit(self.T[0] - self.K[0], self.T[1] - self.K[1])
        self.u3 = _unit(self.T[0] - self.J2[0], self.T[1] - self.J2[1])
        self.start = (self.K[0] - self.u[0] * self.w * root, self.K[1] - self.u[1] * self.w * root)
        w = self.w
        # Stations along the finger: (point, half width). Bulges at the joints
        # and the pad give it a finger's silhouette rather than a tube's.
        self.stations = [
            (self.start, 0.56 * w),
            (self.K, 0.52 * w),
            (_lerp(self.K, self.J1, 0.55), 0.465 * w),
            (self.J1, 0.47 * w),
            (_lerp(self.J1, self.J2, 0.5), 0.42 * w),
            (self.J2, 0.41 * w),
            (_lerp(self.J2, self.T, 0.55), 0.41 * w),
            (self.T, 0.37 * w),
        ]

    def _normals(self):
        out = []
        pts = [p for p, _ in self.stations]
        for i in range(len(pts)):
            a = pts[max(i - 1, 0)]
            b = pts[min(i + 1, len(pts) - 1)]
            tx, ty = _unit(b[0] - a[0], b[1] - a[1])
            out.append((-ty, tx))
        return out

    def path(self, ctx: cairo.Context, grow: float = 0.0) -> None:
        normals = self._normals()
        left = [(p[0] + n[0] * (h + grow), p[1] + n[1] * (h + grow))
                for (p, h), n in zip(self.stations, normals)]
        right = [(p[0] - n[0] * (h + grow), p[1] - n[1] * (h + grow))
                 for (p, h), n in zip(self.stations, normals)]
        ctx.new_path()
        _catmull_rom(ctx, left)
        nx, ny = normals[-1]
        ang = math.atan2(ny, nx)  # the left-hand normal at the tip
        ctx.arc_negative(self.T[0], self.T[1], self.stations[-1][1] + grow, ang, ang - math.pi)
        _catmull_rom(ctx, list(reversed(right)))
        ctx.close_path()


def _side_point(f: Finger, u: float, side: float):
    p = _lerp(f.K, f.J1, u)
    return (p[0] - f.u[1] * f.w * 0.5 * side, p[1] + f.u[0] * f.w * 0.5 * side)


def _palm_points(hand: dict, fingers: dict[str, Finger]):
    wx, wy = hand["wrist"]
    half = hand["wrist_half"]
    names = hand["fingers"]
    first, last = fingers[names[0]], fingers[names[-1]]
    pts = [(wx - 60, wy - half), (wx + 130, wy - half - 16)]
    pts.append((first.K[0] - 60, first.K[1] - first.w * 0.62))
    pts.append(_side_point(first, 0.1, -1))
    # Webbing between neighbouring fingers, a little way up the fingers.
    for a, b in zip(names, names[1:]):
        fa, fb = fingers[a], fingers[b]
        pts.append(_lerp(_lerp(fa.K, fa.J1, 0.12), _lerp(fb.K, fb.J1, 0.12), 0.5))
    pts.append(_side_point(last, 0.1, 1))
    pts.append((last.K[0] - 70, last.K[1] + last.w * 0.8))
    pts.append((wx + 130, wy + half + 16))
    pts.append((wx - 60, wy + half))
    return pts


def _wrist_fade(hand: dict) -> cairo.LinearGradient:
    """Alpha mask that fades the hand out toward the wrist, like a vignette."""
    wx, _ = hand["wrist"]
    g = cairo.LinearGradient(wx + 10, 0, wx + 140, 0)
    g.add_color_stop_rgba(0, 0, 0, 0, 0)
    g.add_color_stop_rgba(0.75, 0, 0, 0, 0.92)
    g.add_color_stop_rgba(1, 0, 0, 0, 1)
    return g


def _finger_fill(ctx: cairo.Context, f: Finger) -> None:
    # Flat skin with a soft shade along the side away from the light (the
    # top of the frame), like a lightly airbrushed cel.
    p = _lerp(f.K, f.J1, 0.6)
    nx, ny = -f.u[1], f.u[0]
    if ny > 0:
        nx, ny = -nx, -ny
    h = f.w * 0.5
    g = cairo.LinearGradient(p[0] + nx * h, p[1] + ny * h, p[0] - nx * h, p[1] - ny * h)
    g.add_color_stop_rgb(0.0, *L.SKIN_LIGHT)
    g.add_color_stop_rgb(0.3, *L.SKIN)
    g.add_color_stop_rgb(0.72, *L.SKIN)
    g.add_color_stop_rgb(1.0, *L.SKIN_SHADE)
    f.path(ctx)
    ctx.set_source(g)
    ctx.fill()


def _arc_across(ctx, center, direction, half, bow) -> None:
    ux, uy = direction
    nx, ny = -uy, ux
    a = (center[0] + nx * half, center[1] + ny * half)
    b = (center[0] - nx * half, center[1] - ny * half)
    ctx.move_to(*a)
    ctx.curve_to(a[0] + ux * bow, a[1] + uy * bow, b[0] + ux * bow, b[1] + uy * bow, *b)


def _finger_details(ctx: cairo.Context, f: Finger) -> None:
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    w = f.w
    u1 = _unit(f.J1[0] - f.K[0], f.J1[1] - f.K[1])
    u2 = _unit(f.J2[0] - f.J1[0], f.J2[1] - f.J1[1])
    # One small crease at each joint, cupped toward the fingertip.
    ctx.new_path()
    _arc_across(ctx, f.J1, u1, w * 0.16, -w * 0.07)
    _arc_across(ctx, f.J2, u2, w * 0.12, -w * 0.05)
    set_rgb(ctx, L.SKIN_LINE, 0.55)
    ctx.set_line_width(1.6)
    ctx.stroke()
    # Nail: a U open toward the knuckle, its free edge at the fingertip.
    nl = w * 0.40 * (1 - 0.3 * f.curl)
    nw = w * 0.46
    ux, uy = f.u3
    cx = f.T[0] - ux * (nl * 0.5 + w * 0.05)
    cy = f.T[1] - uy * (nl * 0.5 + w * 0.05)
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(math.atan2(uy, ux))
    ctx.new_path()
    ctx.move_to(-nl / 2, -nw / 2)
    ctx.line_to(nl * 0.1, -nw / 2)
    ctx.curve_to(nl * 0.62, -nw / 2, nl * 0.62, nw / 2, nl * 0.1, nw / 2)
    ctx.line_to(-nl / 2, nw / 2)
    set_rgb(ctx, L.NAIL_LIGHT)
    ctx.fill_preserve()
    set_rgb(ctx, L.SKIN_LINE, 0.75)
    ctx.set_line_width(1.6)
    ctx.stroke()
    ctx.restore()


def build_fingers(tips, names) -> dict[str, Finger]:
    out = {}
    for f in names:
        tip, _ = tips[f]
        out[f] = Finger(L.KNUCKLES[f], tip, L.FINGER_W[f], rig.FINGER_LEN[f])
    return out


def draw_hand(ctx: cairo.Context, hand_key: str, tips, pose: "rig.Pose", mode: str = "full") -> None:
    """mode 'full' draws the inked, shaded hand; 'silhouette' fills its shape
    with the current source (used for the shadow). Either way the hand fades
    out toward the wrist."""
    hand = L.HANDS[hand_key]
    names = hand["fingers"]
    # Build the hand in its own frame, then let the ctx transform place it.
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
    # Pass 1: one thin, even outline around every part, so the union reads
    # as a single contour once the fills cover the inner halves.
    set_rgb(ctx, L.SKIN_LINE)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_width(4.6)
    ctx.new_path()
    _catmull_rom(ctx, palm, closed=True)
    ctx.stroke()
    for name in reversed(names):
        fingers[name].path(ctx)
        ctx.stroke()

    # Pass 2: back of the hand, flat skin with a gentle shade on the far side.
    ys = [p[1] for p in palm]
    g = cairo.LinearGradient(0, min(ys), 0, max(ys))
    g.add_color_stop_rgb(0, *L.SKIN_LIGHT)
    g.add_color_stop_rgb(0.3, *L.SKIN)
    g.add_color_stop_rgb(0.8, *L.SKIN)
    g.add_color_stop_rgb(1, *L.SKIN_SHADE)
    ctx.new_path()
    _catmull_rom(ctx, palm, closed=True)
    ctx.set_source(g)
    ctx.fill()

    # Pass 3: fingers, pinky first so the index sits on top.
    for name in reversed(names):
        _finger_fill(ctx, fingers[name])
    for name in names:
        _finger_details(ctx, fingers[name])

    # Knuckles: a short light crease behind each.
    ctx.new_path()
    for name in names:
        f = fingers[name]
        c = (f.K[0] - f.u[0] * f.w * 0.35, f.K[1] - f.u[1] * f.w * 0.35)
        _arc_across(ctx, c, (-f.u[0], -f.u[1]), f.w * 0.15, f.w * 0.06)
    set_rgb(ctx, L.SKIN_LINE, 0.45)
    ctx.set_line_width(1.6)
    ctx.stroke()
    ctx.pop_group_to_source()
    ctx.mask(fade)
