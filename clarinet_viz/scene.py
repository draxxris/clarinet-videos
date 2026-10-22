"""Draws one frame of the video: scrolling staff, note highway, clarinet
and the now-playing panel."""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from fractions import Fraction

import cairo
import numpy as np

from . import draw as D
from . import layout as L
from .fingerings import FINGERS, KEYS, fingering_for
from .score import Note, Score

UPCOMING_WINDOW = 0.9  # seconds ahead that keys start glowing
IMPACT_TIME = 0.2      # seconds the "press" burst lasts


@dataclass
class Event:
    start: float  # video time, seconds
    end: float
    note: Note
    fingering: frozenset[str] | None
    by_finger: dict[str, list[str]] = field(default_factory=dict)


def register_name(written_midi: int) -> str:
    if written_midi <= 66:
        return "Chalumeau"
    if written_midi <= 70:
        return "Throat tones"
    if written_midi <= 84:
        return "Clarion"
    return "Altissimo"


class Scene:
    def __init__(self, score: Score, lead_in: float = 2.5, tail: float = 1.5,
                 lookahead: float | None = None, show_concert: bool = True):
        self.score = score
        self.lead_in = lead_in
        self.show_concert = show_concert
        x, _, w, _ = L.HIGHWAY_RECT
        self.pps = L.PX_PER_SEC
        if lookahead:
            self.pps = (x + w - L.STRIKE_X) / lookahead
        self.duration = lead_in + score.duration + tail
        self.events: list[Event] = []
        for n in score.notes:
            fing = fingering_for(n.written_midi)
            by_finger: dict[str, list[str]] = {}
            for k in sorted(fing or ()):
                by_finger.setdefault(KEYS[k].finger, []).append(k)
            self.events.append(Event(n.start + lead_in, n.end + lead_in, n, fing, by_finger))
        self._starts = [e.start for e in self.events]
        self._bg: cairo.ImageSurface | None = None
        self._body: cairo.ImageSurface | None = None

    # ------------------------------------------------------------------ timing

    def current(self, t: float) -> tuple[Event | None, int]:
        """Event sounding at t (or None during a rest), and the index of the next event."""
        i = bisect.bisect_right(self._starts, t) - 1
        cur = self.events[i] if i >= 0 and t < self.events[i].end else None
        return cur, i + 1

    def music_time(self, t: float) -> float:
        return t - self.lead_in

    def beat_at(self, seconds: float) -> float:
        """Inverse of the tempo map (music seconds -> quarter-note beats)."""
        pts = self.score.tempo.points
        acc = 0.0
        for idx, (b, bpm) in enumerate(pts):
            nxt = pts[idx + 1][0] if idx + 1 < len(pts) else None
            seg = float(nxt - b) * 60 / bpm if nxt is not None else math.inf
            if seconds <= acc + seg:
                return float(b) + (seconds - acc) * bpm / 60
            acc += seg
        return 0.0

    def time_x(self, t_video: float, now: float) -> float:
        return L.STRIKE_X + (t_video - now) * self.pps

    # ------------------------------------------------------------------ frame

    def render(self, ctx: cairo.Context, t: float) -> None:
        if self._bg is None:
            self._bg = self._render_background()
            self._body = self._render_body()
            self._overlay = self._render_overlay()
            self._highway = cairo.ImageSurface(cairo.FORMAT_ARGB32, L.W, L.H)
            self._draw_highway_static(cairo.Context(self._highway))
        ctx.set_source_surface(self._bg, 0, 0)
        ctx.paint()
        cur, nxt_i = self.current(t)
        nxt = self.events[nxt_i] if nxt_i < len(self.events) else None

        ctx.set_source_surface(self._body, 0, 0)
        ctx.paint()
        self._draw_keys(ctx, t, cur, nxt)
        ctx.set_source_surface(self._highway, 0, 0)
        ctx.paint()
        self._draw_highway(ctx, t, cur)
        ctx.set_source_surface(self._overlay, 0, 0)
        ctx.paint()
        self._draw_staff_notes(ctx, t, cur)
        self._draw_now(ctx, t, cur, nxt)

    # ------------------------------------------------------------------ static

    def _render_background(self) -> cairo.ImageSurface:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, L.W, L.H)
        ctx = cairo.Context(surf)
        g = cairo.LinearGradient(0, 0, 0, L.H)
        g.add_color_stop_rgb(0, *L.BG_TOP)
        g.add_color_stop_rgb(1, *L.BG_BOTTOM)
        ctx.set_source(g)
        ctx.paint()
        # Faint glow behind the instrument so the black wood reads.
        g = cairo.RadialGradient(L.BODY_X, 600, 30, L.BODY_X, 600, 560)
        g.add_color_stop_rgba(0, 0.55, 0.6, 0.85, 0.22)
        g.add_color_stop_rgba(1, 0.55, 0.6, 0.85, 0)
        ctx.set_source(g)
        ctx.paint()
        # Scattered stars.
        rng = np.random.default_rng(3)
        for _ in range(140):
            sx, sy = rng.uniform(0, L.W), rng.uniform(0, L.H)
            r = rng.choice([1.2, 1.6, 2.2, 3.2], p=[0.45, 0.3, 0.17, 0.08])
            ctx.arc(sx, sy, r, 0, 2 * math.pi)
            D.set_rgb(ctx, L.WHITE, rng.uniform(0.35, 0.9))
            ctx.fill()
        self._draw_lane_guides(ctx)
        return surf

    def _render_overlay(self) -> cairo.ImageSurface:
        """Panels that sit on top of the instrument."""
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, L.W, L.H)
        ctx = cairo.Context(surf)
        self._draw_staff_static(ctx)
        D.panel(ctx, *L.NOW_PANEL, shadow=7, line_w=4)
        return surf

    def _render_body(self) -> cairo.ImageSurface:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, L.W, L.H)
        ctx = cairo.Context(surf)
        self._draw_clarinet_body(ctx)
        return surf

    # staff ------------------------------------------------------------------

    @staticmethod
    def staff_y(step: int) -> float:
        return L.STAFF_BOTTOM_LINE - (step - 2) * L.STAFF_SPACE / 2

    def _draw_staff_static(self, ctx) -> None:
        x, y, w, h = L.STAFF_PANEL
        D.panel(ctx, x, y, w, h, shadow=7, line_w=4)
        title_font, _, music_font = D.fonts()
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(2)
        for i in range(5):
            yy = L.STAFF_BOTTOM_LINE - i * L.STAFF_SPACE
            ctx.move_to(x + 14, yy)
            ctx.line_to(x + w - 14, yy)
        ctx.stroke()
        D.text(ctx, "\U0001D11E", x + 16, L.STAFF_BOTTOM_LINE + 12, 84, font=music_font, bold=False)
        fifths = self.score.key_fifths
        sharp_steps = [10, 7, 11, 8, 5, 9, 6]
        flat_steps = [6, 9, 5, 8, 4, 7, 3]
        kx = x + 78
        for i in range(abs(fifths)):
            step = (sharp_steps if fifths > 0 else flat_steps)[i]
            glyph = "♯" if fifths > 0 else "♭"
            D.text(ctx, glyph, kx + i * 13, self.staff_y(step) + 8, 27, font=music_font, bold=False)
        tx = kx + abs(fifths) * 13 + 8
        beats, beat_type = self.score.time_sig
        D.text(ctx, str(beats), tx, L.STAFF_BOTTOM_LINE - 28, 30, font="DejaVu Serif")
        D.text(ctx, str(beat_type), tx, L.STAFF_BOTTOM_LINE + 2, 30, font="DejaVu Serif")
        cap = f"{self.score.title}  •  Bb clarinet, written pitch"
        ctx.select_font_face(title_font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(19)
        cw = ctx.text_extents(cap).x_advance + 24
        D.rounded_rect(ctx, x + w - cw - 14, y - 6, cw, 30, 4)
        D.fill_ink(ctx, L.STAR, 3)
        D.text(ctx, cap, x + w - cw - 2, y + 15, 19, font=title_font)

    def _draw_staff_notes(self, ctx, t: float, cur: Event | None) -> None:
        x0, y0, w, h = L.STAFF_PANEL
        right = x0 + w - 16
        _, _, music_font = D.fonts()
        m = self.music_time(t)
        t_lo = t - (L.STRIKE_X - L.STAFF_NOTES_LEFT) / self.pps - 1
        t_hi = t + (right - L.STRIKE_X) / self.pps + 1

        ctx.save()
        ctx.rectangle(L.STAFF_NOTES_LEFT, y0 + 3, right - L.STAFF_NOTES_LEFT, h - 6)
        ctx.clip()
        for meas in self.score.measures:
            vt = meas.start + self.lead_in
            if t_lo <= vt <= t_hi:
                bx = self.time_x(vt, t) - 12
                D.set_rgb(ctx, L.INK)
                ctx.set_line_width(2.2)
                ctx.move_to(bx, L.STAFF_BOTTOM_LINE)
                ctx.line_to(bx, L.STAFF_BOTTOM_LINE - 4 * L.STAFF_SPACE)
                ctx.stroke()
                D.text(ctx, meas.number, bx - 4, L.STAFF_BOTTOM_LINE - 4 * L.STAFF_SPACE - 6, 13,
                       align="right", color=D.lighten(L.INK, 0.45))
        for ev in self.events:
            if ev.end < t_lo or ev.start > t_hi:
                continue
            n = ev.note
            nx = self.time_x(ev.start, t)
            ny = self.staff_y(n.staff_step)
            playing = ev is cur
            past = ev.end <= t
            color = L.ACCENT if playing else (D.lighten(L.INK, 0.6) if past else L.INK)
            D.rounded_rect(ctx, nx, ny - 4.5, max(6, (ev.end - ev.start) * self.pps - 6), 9, 4.5)
            D.set_rgb(ctx, L.ACCENT if playing else (0.55, 0.55, 0.7), 0.3 if not past else 0.12)
            ctx.fill()
            self._draw_notehead(ctx, nx, ny, n, color, music_font, glow=playing)
        for r in self.score.rests:
            vt = r.start + self.lead_in
            if t_lo <= vt <= t_hi:
                glyph = {"whole": "\U0001D13B", "half": "\U0001D13C", "quarter": "\U0001D13D",
                         "eighth": "\U0001D13E", "16th": "\U0001D13F"}.get(r.note_type or "", "\U0001D13D")
                D.text(ctx, glyph, self.time_x(vt, t), self.staff_y(6) + 10, 36, font=music_font,
                       bold=False, color=D.lighten(L.INK, 0.6) if r.end + self.lead_in <= t else L.INK)
        ctx.restore()

        # Playhead lines up with the highway's strike line.
        D.set_rgb(ctx, L.ACCENT)
        ctx.set_line_width(3)
        ctx.move_to(L.STRIKE_X, y0 + 10)
        ctx.line_to(L.STRIKE_X, y0 + h - 14)
        ctx.stroke()
        frac = min(1.0, max(0.0, m / max(self.score.duration, 1e-6)))
        D.rounded_rect(ctx, x0 + 14, y0 + h - 10, w - 28, 5, 2.5)
        D.set_rgb(ctx, (0.86, 0.86, 0.86))
        ctx.fill()
        D.rounded_rect(ctx, x0 + 14, y0 + h - 10, (w - 28) * frac, 5, 2.5)
        D.set_rgb(ctx, L.ACCENT)
        ctx.fill()

        # Note-name tags between the staff and the lanes.
        ctx.save()
        hx, hy, hw, hh = L.HIGHWAY_RECT
        ctx.rectangle(L.STRIKE_X - 30, y0 + h, hx + hw - L.STRIKE_X + 30, hy - y0 - h + 4)
        ctx.clip()
        title_font = D.fonts()[0]
        for ev in self.events:
            if ev.end < t or ev.start > t_hi:
                continue
            nx = max(self.time_x(ev.start, t), L.STRIKE_X - 26) if ev is cur else self.time_x(ev.start, t)
            name = ev.note.name if ev.fingering is not None else ev.note.name + "?"
            ctx.select_font_face(title_font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(17)
            tw = ctx.text_extents(name).x_advance + 12
            D.rounded_rect(ctx, nx - 4, L.NAME_ROW_Y - 11, tw, 22, 5)
            D.fill_ink(ctx, L.ACCENT if ev is cur else L.STAR, 2)
            D.text(ctx, name, nx - 4 + tw / 2, L.NAME_ROW_Y + 6, 17, align="center", font=title_font,
                   color=L.WHITE if ev is cur else L.INK)
        ctx.restore()

    def _draw_notehead(self, ctx, nx, ny, n: Note, color, music_font, glow=False) -> None:
        step = n.staff_step
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(2)
        ledgers = list(range(0, step - 1, -2)) if step <= 0 else list(range(12, step + 1, 2))
        for s in ledgers:
            ctx.move_to(nx - 14, self.staff_y(s))
            ctx.line_to(nx + 14, self.staff_y(s))
        ctx.stroke()
        if glow:
            ctx.arc(nx, ny, 17, 0, 2 * math.pi)
            D.set_rgb(ctx, L.STAR, 0.9)
            ctx.fill()
        hollow = n.note_type in ("half", "whole")
        ctx.save()
        ctx.translate(nx, ny)
        ctx.rotate(-0.35)
        ctx.scale(1.0, 0.72)
        ctx.arc(0, 0, 8.6, 0, 2 * math.pi)
        ctx.restore()
        D.set_rgb(ctx, color)
        if hollow:
            ctx.set_line_width(3.2)
            ctx.stroke()
        else:
            ctx.fill()
        if n.note_type != "whole":
            up = step < 6
            ctx.set_line_width(2.2)
            sx_ = nx + 7.8 if up else nx - 7.8
            tip = ny - 44 if up else ny + 44
            ctx.move_to(sx_, ny)
            ctx.line_to(sx_, tip)
            ctx.stroke()
            flags = {"eighth": 1, "16th": 2, "32nd": 3}.get(n.note_type or "", 0)
            d = 1 if up else -1
            for i in range(flags):
                fy = tip + i * 9 * d
                ctx.move_to(sx_, fy)
                ctx.curve_to(sx_ + 4, fy + 9 * d, sx_ + 15, fy + 13 * d, sx_ + 9, fy + 26 * d)
                ctx.set_line_width(2.8)
                ctx.stroke()
        for i in range(n.dots):
            ctx.arc(nx + 15 + i * 7, ny - (3 if step % 2 == 0 else 0), 2.4, 0, 2 * math.pi)
            ctx.fill()
        if n.accidental:
            glyph = {"sharp": "♯", "flat": "♭", "natural": "♮",
                     "double-sharp": "\U0001D12A", "flat-flat": "\U0001D12B"}.get(n.accidental)
            if glyph:
                D.text(ctx, glyph, nx - 27, ny + 7, 24, color=color, font=music_font, bold=False)

    # highway -----------------------------------------------------------------

    def _draw_lane_guides(self, ctx) -> None:
        """Dashed guides from each finger's keys toward its lane."""
        for f in FINGERS:
            ly = L.LANE_Y[f]
            ctx.move_to(L.BODY_RIGHT + 14, ly)
            ctx.line_to(L.STRIKE_X - 26, ly)
            ctx.set_dash([4, 6])
            D.set_rgb(ctx, D.darken(L.FINGER_COLORS[f], 0.2), 0.7)
            ctx.set_line_width(2.5)
            ctx.stroke()
            ctx.set_dash([])

    def _draw_highway_static(self, ctx) -> None:
        x, y, w, h = L.HIGHWAY_RECT
        D.rounded_rect(ctx, x, y, w, h, 16)
        g = cairo.LinearGradient(x, 0, x + w, 0)
        g.add_color_stop_rgb(0, *D.lighten(L.HIGHWAY, 0.06))
        g.add_color_stop_rgb(1, *D.darken(L.HIGHWAY, 0.25))
        ctx.set_source(g)
        ctx.fill_preserve()
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(4)
        ctx.stroke()
        _, text_font, _ = D.fonts()
        for f in FINGERS:
            ly = L.LANE_Y[f]
            c = L.FINGER_COLORS[f]
            D.rounded_rect(ctx, x + 8, ly - L.LANE_H / 2, w - 16, L.LANE_H, 12)
            D.set_rgb(ctx, L.HIGHWAY_LANE)
            ctx.fill()
            ctx.move_to(L.STRIKE_X, ly)
            ctx.line_to(x + w - 10, ly)
            D.set_rgb(ctx, c, 0.28)
            ctx.set_line_width(2)
            ctx.stroke()
            D.text(ctx, L.FINGER_LABELS[f].upper(), L.STRIKE_X + 32, ly - L.LANE_H / 2 + 14, 12,
                   color=c, font=text_font)
        # Strike line.
        ctx.move_to(L.STRIKE_X, y + 6)
        ctx.line_to(L.STRIKE_X, y + h - 6)
        D.set_rgb(ctx, L.WHITE, 0.85)
        ctx.set_line_width(4)
        ctx.stroke()

    def _draw_highway(self, ctx, t: float, cur: Event | None) -> None:
        x, y, w, h = L.HIGHWAY_RECT
        right = x + w - 8
        t_hi = t + (right - L.STRIKE_X) / self.pps
        ctx.save()
        D.rounded_rect(ctx, L.STRIKE_X, y + 4, right - L.STRIKE_X, h - 8, 12)
        ctx.clip()
        # Beat and bar lines.
        bar_starts = {float(ms.start_beat) for ms in self.score.measures}
        m = self.music_time(t)
        b = math.floor(self.beat_at(max(0.0, m)))
        b_end = min(self.beat_at(max(0.0, t_hi - self.lead_in)) + 1, float(self.score.total_beats))
        while b <= b_end:
            vt = self.score.tempo.seconds(Fraction(b).limit_denominator(64)) + self.lead_in
            if t <= vt <= t_hi:
                bx = self.time_x(vt, t)
                is_bar = float(b) in bar_starts
                ctx.move_to(bx, y + 6)
                ctx.line_to(bx, y + h - 6)
                D.set_rgb(ctx, L.WHITE, 0.32 if is_bar else 0.09)
                ctx.set_line_width(3 if is_bar else 1.5)
                ctx.stroke()
            b += 1
        for ev in self.events:
            if ev.end > t and ev.start < t_hi:
                self._draw_gems(ctx, t, ev)
        ctx.restore()

        active = cur.by_finger if cur else {}
        for f in FINGERS:
            ly = L.LANE_Y[f]
            c = L.FINGER_COLORS[f]
            on = f in active
            if on:
                age = t - cur.start
                g = cairo.RadialGradient(L.STRIKE_X, ly, 10, L.STRIKE_X, ly, 62)
                g.add_color_stop_rgba(0, *c, 0.7)
                g.add_color_stop_rgba(1, *c, 0.0)
                ctx.set_source(g)
                ctx.arc(L.STRIKE_X, ly, 62, 0, 2 * math.pi)
                ctx.fill()
                if age < IMPACT_TIME:
                    self._impact(ctx, L.STRIKE_X, ly, c, age / IMPACT_TIME)
            ctx.arc(L.STRIKE_X, ly, 24, 0, 2 * math.pi)
            D.set_rgb(ctx, c if on else D.darken(c, 0.6))
            ctx.fill_preserve()
            D.set_rgb(ctx, L.INK)
            ctx.set_line_width(3.5)
            ctx.stroke()
            ctx.arc(L.STRIKE_X, ly, 13, 0, 2 * math.pi)
            D.set_rgb(ctx, L.WHITE, 0.9 if on else 0.18)
            ctx.fill()

    def _gem_label(self, finger: str, keys: list[str]) -> str:
        if finger == "LT":
            return "+".join(["T"] * ("T" in keys) + ["Reg"] * ("REG" in keys))
        return "+".join(L.SHORT_LABELS[k] for k in keys if KEYS[k].kind == "key")

    def _draw_gems(self, ctx, t: float, ev: Event) -> None:
        dur = ev.end - ev.start
        gap = min(0.06, dur * 0.2)
        x0 = self.time_x(ev.start, t)
        x1 = self.time_x(ev.end - gap, t)
        if x1 <= L.STRIKE_X:
            return
        started = x0 < L.STRIKE_X
        xa = max(x0, L.STRIKE_X - 4)
        title_font = D.fonts()[0]
        for f, keys in (ev.by_finger.items() if ev.fingering is not None else []):
            c = L.FINGER_COLORS[f]
            ly = L.LANE_Y[f]
            gh = L.GEM_H
            D.rounded_rect(ctx, xa, ly - gh / 2, max(gh, x1 - xa), gh, 13)
            g = cairo.LinearGradient(0, ly - gh / 2, 0, ly + gh / 2)
            top = D.lighten(c, 0.45 if started else 0.25)
            g.add_color_stop_rgb(0, *top)
            g.add_color_stop_rgb(0.5, *c)
            g.add_color_stop_rgb(1, *D.darken(c, 0.35))
            ctx.set_source(g)
            ctx.fill_preserve()
            D.set_rgb(ctx, L.INK)
            ctx.set_line_width(2.5)
            ctx.stroke()
            D.rounded_rect(ctx, xa + 8, ly - gh / 2 + 5, max(10, x1 - xa - 16), 7, 3.5)
            D.set_rgb(ctx, L.WHITE, 0.5)
            ctx.fill()
            label = self._gem_label(f, keys)
            if label:
                # The label rides the front of the gem, then sticks just past the strike line.
                lx = max(x0 + 12, L.STRIKE_X + 32)
                if lx < x1 - 20:
                    D.text(ctx, label, lx, ly + 8, 22, color=L.WHITE, font=title_font, outline=4)

    def _impact(self, ctx, x, y, col, u: float) -> None:
        r0 = 30 + 18 * u
        r1 = r0 + 16 * (1 - u)
        ctx.save()
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for i in range(8):
            a = i * math.pi / 4 + 0.3
            ctx.move_to(x + r0 * math.cos(a), y + r0 * math.sin(a))
            ctx.line_to(x + r1 * math.cos(a), y + r1 * math.sin(a))
        D.set_rgb(ctx, col, 1 - u)
        ctx.set_line_width(4)
        ctx.stroke()
        ctx.restore()

    # clarinet ----------------------------------------------------------------

    def _draw_clarinet_body(self, ctx) -> None:
        top, bottom = -20, L.H + 20
        xl, xr = L.BODY_LEFT, L.BODY_RIGHT
        # Cast shadow of the instrument on the backdrop.
        for i in range(10):
            D.rounded_rect(ctx, xl + 14 - i * 2, top, (xr - xl) + i * 4, bottom - top, 30)
            D.set_rgb(ctx, (0.2, 0.15, 0.1), 0.025)
            ctx.fill()
        # Wooden tube, shaded as a cylinder lit from the upper left.
        ctx.rectangle(xl, top, xr - xl, bottom - top)
        g = cairo.LinearGradient(xl, 0, xr, 0)
        for stop, col in ((0, L.WOOD_EDGE), (0.12, L.WOOD), (0.24, L.WOOD_MID), (0.3, L.WOOD_SHINE),
                          (0.36, L.WOOD_MID), (0.55, L.WOOD), (0.88, D.darken(L.WOOD, 0.5)),
                          (1, L.WOOD_EDGE)):
            g.add_color_stop_rgb(stop, *col)
        ctx.set_source(g)
        ctx.fill()
        # Grenadilla grain.
        rng = np.random.default_rng(7)
        for _ in range(70):
            gx = rng.uniform(xl + 6, xr - 6)
            gy = rng.uniform(top, bottom)
            ln = rng.uniform(40, 220)
            ctx.move_to(gx, gy)
            ctx.curve_to(gx + rng.uniform(-2, 2), gy + ln / 3, gx + rng.uniform(-2, 2), gy + 2 * ln / 3,
                         gx + rng.uniform(-1.5, 1.5), gy + ln)
            D.set_rgb(ctx, L.WHITE, rng.uniform(0.02, 0.06))
            ctx.set_line_width(rng.uniform(0.8, 1.8))
            ctx.stroke()
        # Metal tenon rings: top of the upper joint and the middle joint.
        for ry, rh in ((150, 20), (L.TENON_Y - 14, 12), (L.TENON_Y + 4, 12)):
            self._ring(ctx, ry, rh)
        # Key rods along the right side, with posts.
        for y0, y1 in ((230, 530), (596, 950)):
            self._metal_bar(ctx, xr - 10, y0, 7, y1 - y0, vertical=True)
            for py in (y0, y1):
                ctx.arc(xr - 6.5, py, 7, 0, 2 * math.pi)
                self._metal_fill(ctx, xr - 13, xr)
        # Ring-key linkages from each hole to the rod.
        for k in ("L1", "L2", "L3", "R1", "R2", "R3"):
            hx, hy, _ = L.KEY_POS[k]
            self._metal_bar(ctx, hx + L.HOLE_R + 4, hy - 3, xr - 10 - (hx + L.HOLE_R + 4), 6)
        # Thumb rest on the back (dashed: it's behind).
        ctx.save()
        ctx.set_dash([6, 5])
        D.rounded_rect(ctx, L.BODY_X - 30, L.THUMB_REST_Y - 16, 60, 32, 9)
        D.set_rgb(ctx, L.SILVER, 0.35)
        ctx.fill_preserve()
        D.set_rgb(ctx, L.SILVER, 0.8)
        ctx.set_line_width(2.5)
        ctx.stroke()
        ctx.restore()
        # Outline.
        ctx.move_to(xl, top)
        ctx.line_to(xl, bottom)
        ctx.move_to(xr, top)
        ctx.line_to(xr, bottom)
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(3)
        ctx.stroke()

    def _metal_fill(self, ctx, x0, x1) -> None:
        g = cairo.LinearGradient(x0, 0, x1, 0)
        g.add_color_stop_rgb(0, *L.SILVER_SHADE)
        g.add_color_stop_rgb(0.35, *L.SILVER_LIGHT)
        g.add_color_stop_rgb(0.7, *L.SILVER)
        g.add_color_stop_rgb(1, *L.SILVER_DARK)
        ctx.set_source(g)
        ctx.fill_preserve()
        D.set_rgb(ctx, L.INK, 0.85)
        ctx.set_line_width(1.6)
        ctx.stroke()

    def _metal_bar(self, ctx, x, y, w, h, vertical=False) -> None:
        D.rounded_rect(ctx, x, y, w, h, min(w, h) / 2)
        if vertical:
            self._metal_fill(ctx, x, x + w)
        else:
            g = cairo.LinearGradient(0, y, 0, y + h)
            g.add_color_stop_rgb(0, *L.SILVER_LIGHT)
            g.add_color_stop_rgb(1, *L.SILVER_SHADE)
            ctx.set_source(g)
            ctx.fill_preserve()
            D.set_rgb(ctx, L.INK, 0.85)
            ctx.set_line_width(1.4)
            ctx.stroke()

    def _ring(self, ctx, y, h) -> None:
        ctx.rectangle(L.BODY_LEFT - 3, y, L.BODY_RIGHT - L.BODY_LEFT + 6, h)
        self._metal_fill(ctx, L.BODY_LEFT - 3, L.BODY_RIGHT + 3)

    def _key_outline(self, ctx, key: str, grow: float = 0.0) -> None:
        x, y, kind = L.KEY_POS[key]
        g = grow
        if kind == "hole":
            ctx.arc(x, y, L.HOLE_R + 7 + g, 0, 2 * math.pi)
        elif kind == "back_hole":
            ctx.arc(x, y, L.HOLE_R + g, 0, 2 * math.pi)
        elif kind == "back_key":
            D.rounded_rect(ctx, x - 26 - g, y - 12 - g, 52 + 2 * g, 24 + 2 * g, 11 + g)
        elif kind == "front_lever":
            D.rounded_rect(ctx, x - 30 - g, y - 11 - g, 60 + 2 * g, 22 + 2 * g, 10 + g)
        elif kind == "side_lever":
            D.rounded_rect(ctx, x - 9 - g, y - 24 - g, 22 + 2 * g, 48 + 2 * g, 9 + g)
        elif kind == "side":
            D.rounded_rect(ctx, x - 7 - g, y - 10 - g, 18 + 2 * g, 20 + 2 * g, 6 + g)
        elif kind == "spatula":
            D.rounded_rect(ctx, x - 26 - g, y - 12 - g, 50 + 2 * g, 24 + 2 * g, 10 + g)

    def _draw_keys(self, ctx, t: float, cur: Event | None, nxt: Event | None) -> None:
        pressed = (cur.fingering or frozenset()) if cur else frozenset()
        upcoming: frozenset[str] = frozenset()
        u_amt = 0.0
        if nxt is not None and nxt.fingering is not None:
            lead = nxt.start - t
            if lead <= UPCOMING_WINDOW:
                upcoming = nxt.fingering
                u_amt = 1 - lead / UPCOMING_WINDOW
        text_font = D.fonts()[1]
        for key, (x, y, kind) in L.KEY_POS.items():
            col = L.FINGER_COLORS[KEYS[key].finger]
            on = key in pressed
            back = kind.startswith("back")
            if on:
                g = cairo.RadialGradient(x, y, 8, x, y, 64)
                g.add_color_stop_rgba(0, *col, 0.85)
                g.add_color_stop_rgba(1, *col, 0.0)
                ctx.set_source(g)
                ctx.arc(x, y, 64, 0, 2 * math.pi)
                ctx.fill()
            if key in upcoming:
                pulse = 0.5 + 0.5 * math.sin(t * 16)
                self._key_outline(ctx, key, 7 + 5 * u_amt)
                D.set_rgb(ctx, col, 0.3 + 0.6 * u_amt * (0.6 + 0.4 * pulse))
                ctx.set_line_width(4 + 3 * u_amt)
                ctx.stroke()
            if kind == "hole":
                # Ring key around an open tone hole.
                ctx.arc(x, y, L.HOLE_R + 7, 0, 2 * math.pi)
                ctx.arc_negative(x, y, L.HOLE_R + 1, 2 * math.pi, 0)
                if on:
                    D.set_rgb(ctx, col)
                    ctx.fill()
                else:
                    self._metal_fill(ctx, x - L.HOLE_R - 7, x + L.HOLE_R + 7)
                    ctx.new_path()
                ctx.arc(x, y, L.HOLE_R, 0, 2 * math.pi)
                if on:
                    # Covered: the hole is filled in with the finger's colour.
                    g = cairo.RadialGradient(x - 6, y - 6, 2, x, y, L.HOLE_R)
                    g.add_color_stop_rgb(0, *D.lighten(col, 0.6))
                    g.add_color_stop_rgb(1, *col)
                    ctx.set_source(g)
                    ctx.fill_preserve()
                    D.set_rgb(ctx, L.INK)
                    ctx.set_line_width(2.5)
                    ctx.stroke()
                    continue
                g = cairo.RadialGradient(x - 4, y - 4, 2, x, y, L.HOLE_R)
                g.add_color_stop_rgb(0, 0.0, 0.0, 0.0)
                g.add_color_stop_rgb(0.75, 0.05, 0.05, 0.07)
                g.add_color_stop_rgb(1, 0.22, 0.22, 0.26)
                ctx.set_source(g)
                ctx.fill()
                continue
            if kind == "spatula":
                if x < L.BODY_X:
                    self._metal_bar(ctx, x + 18, y - 3, L.BODY_LEFT - x - 14, 6)
                else:
                    self._metal_bar(ctx, L.BODY_RIGHT - 4, y - 3, x - 14 - L.BODY_RIGHT, 6)
            ctx.save()
            if back:
                ctx.set_dash([5, 4])
            self._key_outline(ctx, key)
            if on:
                D.set_rgb(ctx, col, 0.95)
                ctx.fill_preserve()
                D.set_rgb(ctx, L.INK)
                ctx.set_line_width(2)
                ctx.stroke()
            elif back:
                D.set_rgb(ctx, L.SILVER, 0.12)
                ctx.fill_preserve()
                D.set_rgb(ctx, L.SILVER, 0.75)
                ctx.set_line_width(2.2)
                ctx.stroke()
            else:
                ext = {"front_lever": 30, "side_lever": 11, "side": 9, "spatula": 26}[kind]
                self._metal_fill(ctx, x - ext, x + ext)
            ctx.restore()
            label = L.SHORT_LABELS.get(key, "")
            if kind in ("back_key", "back_hole", "front_lever", "spatula"):
                D.text(ctx, label, x, y + 5, 13, align="center", font=text_font,
                       color=L.WHITE if (on or back) else L.INK)
            elif kind == "side_lever" or key == "S4":
                D.text(ctx, label, x + 18, y + 5, 13, font=text_font, color=L.INK)

    # panel -------------------------------------------------------------------

    def _draw_now(self, ctx, t: float, cur: Event | None, nxt: Event | None) -> None:
        x, y, w, h = L.NOW_PANEL
        title_font, text_font, _ = D.fonts()
        if t < self.lead_in and self.events:
            big, sub, col = "READY?", f"first note in {self.events[0].start - t:0.1f}s", L.INK
        elif cur is None:
            big, sub, col = ("REST", "breathe", D.lighten(L.INK, 0.4)) if nxt else ("FIN!", "nice playing", L.INK)
        else:
            big = cur.note.name
            sub = f"sounds {cur.note.concert_name} (concert)" if self.show_concert else ""
            col = L.ACCENT
        age = (t - cur.start) if cur else 1.0
        pop = 1 + 0.1 * max(0.0, 1 - age / 0.15)
        size = (80 if len(big) <= 3 else 56) * pop
        D.text(ctx, big, x + 22, y + 96, size, color=col, font=title_font)
        tx = x + 200
        D.text(ctx, sub, tx, y + 50, 18, font=text_font)
        if cur is not None:
            D.text(ctx, register_name(cur.note.written_midi).upper(), tx, y + 76, 16,
                   color=L.ACCENT, font=title_font)
        if nxt is not None:
            beat_len = 60 / self.score.tempo.bpm_at(Fraction(0))
            D.text(ctx, f"next: {nxt.note.name}  in {(nxt.start - t) / beat_len:0.1f} beats",
                   tx, y + 102, 16, font=text_font, color=D.lighten(L.INK, 0.25))
        m = self.music_time(t)
        bar = "-"
        for meas in self.score.measures:
            if meas.start <= max(m, 0):
                bar = meas.number
        bpm = self.score.tempo.bpm_at(Fraction(self.beat_at(max(m, 0.0))).limit_denominator(64))
        D.text(ctx, f"bar {bar}  •  {bpm:.0f} bpm", x + 24, y + h - 18, 15, font=text_font,
               color=D.lighten(L.INK, 0.35))
