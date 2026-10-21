"""Draws one frame of the video: scrolling staff, note highway, clarinet,
hands and info panels."""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from fractions import Fraction

import cairo

from . import draw as D
from . import layout as L
from .fingerings import FINGERS, KEYS, fingering_for
from .score import Note, Score

TRANS = 0.075          # seconds a finger takes to move to its next position
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
                 lookahead: float = 2.8, show_concert: bool = True):
        self.score = score
        self.lead_in = lead_in
        self.lookahead = lookahead
        self.show_concert = show_concert
        self.duration = lead_in + score.duration + tail
        self.events: list[Event] = []
        for n in score.notes:
            fing = fingering_for(n.written_midi)
            by_finger: dict[str, list[str]] = {}
            for k in sorted(fing or ()):
                by_finger.setdefault(KEYS[k].finger, []).append(k)
            self.events.append(Event(n.start + lead_in, n.end + lead_in, n, fing, by_finger))
        self._starts = [e.start for e in self.events]
        self._build_finger_tracks()
        self._bg: cairo.ImageSurface | None = None

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

    # ------------------------------------------------------------------ fingers

    def _press_pose(self, finger: str, keys: list[str]) -> tuple[float, float]:
        pts = [L.KEY_POS[k] for k in keys]
        if finger == "LT" and set(keys) == {"T", "REG"}:
            # Thumb covers the hole and rolls up onto the register key.
            return ((pts[0][0] + pts[1][0]) / 2, L.BODY_Y + 2)
        holes = [p for p in pts if p[2] in ("hole", "back_hole")]
        if holes:
            return holes[0][0], holes[0][1]
        x = sum(p[0] for p in pts) / len(pts)
        y = sum(p[1] for p in pts) / len(pts)
        return x, y

    def _build_finger_tracks(self) -> None:
        self.tracks: dict[str, list[tuple[float, tuple[float, float], bool]]] = {}
        for f in FINGERS:
            hover = L.HOVER[f]
            track = [(-1e9, hover, False)]
            for i, ev in enumerate(self.events):
                keys = ev.by_finger.get(f)
                pose = self._press_pose(f, keys) if keys else hover
                track.append((ev.start, pose, bool(keys)))
                nxt = self.events[i + 1].start if i + 1 < len(self.events) else math.inf
                if nxt - ev.end > 3 * TRANS:
                    track.append((ev.end + TRANS, hover, False))
            self.tracks[f] = track

    def finger_tip(self, finger: str, t: float) -> tuple[tuple[float, float], float]:
        """Fingertip position at t, and how 'pressed' it is (0..1)."""
        track = self.tracks[finger]
        times = [k[0] for k in track]
        i = bisect.bisect_right(times, t) - 1
        t0, p0, on0 = track[i]
        if i + 1 >= len(track):
            return p0, float(on0)
        t1, p1, on1 = track[i + 1]
        window = min(TRANS, (t1 - t0) * 0.5)
        u = D.smoothstep((t - (t1 - window)) / window) if window > 0 else 0.0
        if p0 != p1 and 0 < u < 1:
            # Lift slightly while travelling between two keys.
            lift = math.sin(u * math.pi) * (14 if on0 and on1 else 0)
        else:
            lift = 0.0
        pos = (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u + lift)
        return pos, float(on0) + (float(on1) - float(on0)) * u

    # ------------------------------------------------------------------ frame

    def render(self, ctx: cairo.Context, t: float) -> None:
        if self._bg is None:
            self._bg = self._render_background()
        ctx.set_source_surface(self._bg, 0, 0)
        ctx.paint()
        cur, nxt_i = self.current(t)
        nxt = self.events[nxt_i] if nxt_i < len(self.events) else None
        self._draw_staff_notes(ctx, t, cur)
        self._draw_highway(ctx, t, cur)
        self._draw_keys(ctx, t, cur, nxt)
        self._draw_hands(ctx, t)
        self._draw_info(ctx, t, cur, nxt)
        self._draw_next(ctx, t, nxt_i)

    # ------------------------------------------------------------------ static

    def _render_background(self) -> cairo.ImageSurface:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, L.W, L.H)
        ctx = cairo.Context(surf)
        D.set_rgb(ctx, L.PAPER)
        ctx.paint()
        D.halftone(ctx, 0, 0, L.W, L.H, L.PAPER_DOT, spacing=18, rmax=5.0,
                   cx=L.W / 2, cy=L.STRIKE_Y, falloff=1150)
        self._draw_speed_lines(ctx)
        self._draw_staff_static(ctx)
        self._draw_highway_static(ctx)
        self._draw_clarinet_body(ctx)
        D.panel(ctx, *L.INFO_PANEL)
        D.panel(ctx, *L.NEXT_PANEL)
        return surf

    def _draw_speed_lines(self, ctx) -> None:
        # Faint comic "focus lines" radiating from the highway's vanishing point.
        cx, cy = L.HIGHWAY_CX, L.HIGHWAY_TOP - 260
        D.set_rgb(ctx, D.darken(L.PAPER, 0.06))
        for i in range(48):
            a = math.pi * (0.08 + 0.84 * i / 47)
            w = 0.012
            ctx.move_to(cx, cy)
            ctx.line_to(cx + 2400 * math.cos(a - w), cy + 2400 * math.sin(a - w))
            ctx.line_to(cx + 2400 * math.cos(a + w), cy + 2400 * math.sin(a + w))
            ctx.close_path()
            ctx.fill()

    # staff ------------------------------------------------------------------

    @staticmethod
    def staff_y(step: int) -> float:
        return L.STAFF_BOTTOM_LINE - (step - 2) * L.STAFF_SPACE / 2

    def _draw_staff_static(self, ctx) -> None:
        x, y, w, h = L.STAFF_PANEL
        D.panel(ctx, x, y, w, h)
        title_font, _, music_font = D.fonts()
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(2.2)
        for i in range(5):
            yy = L.STAFF_BOTTOM_LINE - i * L.STAFF_SPACE
            ctx.move_to(x + 20, yy)
            ctx.line_to(x + w - 20, yy)
        ctx.stroke()
        # Treble clef, key and time signature.
        D.text(ctx, "\U0001D11E", x + 30, L.STAFF_BOTTOM_LINE + 13, 92, font=music_font, bold=False)
        fifths = self.score.key_fifths
        sharp_steps = [10, 7, 11, 8, 5, 9, 6]
        flat_steps = [6, 9, 5, 8, 4, 7, 3]
        kx = x + 102
        for i in range(abs(fifths)):
            step = (sharp_steps if fifths > 0 else flat_steps)[i]
            glyph = "♯" if fifths > 0 else "♭"
            D.text(ctx, glyph, kx + i * 15, self.staff_y(step) + 9, 30, font=music_font, bold=False)
        tx = kx + abs(fifths) * 15 + 14
        beats, beat_type = self.score.time_sig
        D.text(ctx, str(beats), tx, L.STAFF_BOTTOM_LINE - 30, 32, font="DejaVu Serif")
        D.text(ctx, str(beat_type), tx, L.STAFF_BOTTOM_LINE + 2, 32, font="DejaVu Serif")
        # Caption box with the title.
        cap = f"{self.score.title}  •  Bb clarinet (written pitch)"
        ctx.select_font_face(title_font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(22)
        cw = ctx.text_extents(cap).x_advance + 28
        D.rounded_rect(ctx, x + w - cw - 16, y - 8, cw, 34, 4)
        D.fill_ink(ctx, L.STAR, 4)
        D.text(ctx, cap, x + w - cw - 2, y + 17, 22, font=title_font)

    def _draw_staff_notes(self, ctx, t: float, cur: Event | None) -> None:
        x0, y0, w, h = L.STAFF_PANEL
        m = self.music_time(t)
        right = x0 + w - 24
        pps = L.STAFF_PX_PER_SEC
        t_lo = m - (L.STAFF_PLAYHEAD - L.STAFF_LEFT) / pps
        t_hi = m + (right - L.STAFF_PLAYHEAD) / pps
        _, _, music_font = D.fonts()

        def sx(sec: float) -> float:
            return L.STAFF_PLAYHEAD + (sec - m) * pps

        ctx.save()
        ctx.rectangle(L.STAFF_LEFT, y0 + 4, right - L.STAFF_LEFT, h - 8)
        ctx.clip()

        # Bar lines and numbers.
        for meas in self.score.measures:
            if t_lo - 1 <= meas.start <= t_hi:
                bx = sx(meas.start)
                D.set_rgb(ctx, L.INK)
                ctx.set_line_width(2.5)
                ctx.move_to(bx - 14, L.STAFF_BOTTOM_LINE)
                ctx.line_to(bx - 14, L.STAFF_BOTTOM_LINE - 4 * L.STAFF_SPACE)
                ctx.stroke()
                D.text(ctx, meas.number, bx - 18, L.STAFF_BOTTOM_LINE - 4 * L.STAFF_SPACE - 6, 14, align="right",
                       color=D.lighten(L.INK, 0.4))

        for ev in self.events:
            n = ev.note
            if n.end < t_lo - 0.5 or n.start > t_hi + 0.5:
                continue
            nx = sx(n.start)
            ny = self.staff_y(n.staff_step)
            playing = ev is cur
            past = n.end <= m
            color = L.ACCENT if playing else (D.lighten(L.INK, 0.55) if past else L.INK)
            # Duration band: shows how long the note is held, in real time.
            band_col = L.FINGER_COLORS["L2"] if playing else (0.6, 0.6, 0.75)
            D.rounded_rect(ctx, nx, ny - 5, max(6, (n.end - n.start) * pps - 6), 10, 5)
            D.set_rgb(ctx, band_col, 0.35 if not past else 0.15)
            ctx.fill()
            self._draw_notehead(ctx, nx, ny, n, color, music_font, glow=playing)

        # Rests.
        for r in self.score.rests:
            if t_lo - 0.5 <= r.start <= t_hi + 0.5:
                glyph = {"whole": "\U0001D13B", "half": "\U0001D13C", "quarter": "\U0001D13D",
                         "eighth": "\U0001D13E", "16th": "\U0001D13F"}.get(r.note_type or "", "\U0001D13D")
                past = r.end <= m
                D.text(ctx, glyph, sx(r.start), self.staff_y(6) + 10, 40, font=music_font, bold=False,
                       color=D.lighten(L.INK, 0.55) if past else L.INK)
        ctx.restore()

        # Playhead.
        D.set_rgb(ctx, L.ACCENT)
        ctx.set_line_width(4)
        ctx.move_to(L.STAFF_PLAYHEAD - 8, y0 + 14)
        ctx.line_to(L.STAFF_PLAYHEAD - 8, y0 + h - 14)
        ctx.stroke()
        ctx.move_to(L.STAFF_PLAYHEAD - 18, y0 + 4)
        ctx.line_to(L.STAFF_PLAYHEAD + 2, y0 + 4)
        ctx.line_to(L.STAFF_PLAYHEAD - 8, y0 + 18)
        ctx.close_path()
        D.fill_ink(ctx, L.ACCENT, 2.5)
        # Progress bar along the bottom edge of the panel.
        frac = min(1.0, max(0.0, m / max(self.score.duration, 1e-6)))
        D.rounded_rect(ctx, x0 + 20, y0 + h - 12, (w - 40), 6, 3)
        D.set_rgb(ctx, (0.85, 0.85, 0.85))
        ctx.fill()
        D.rounded_rect(ctx, x0 + 20, y0 + h - 12, (w - 40) * frac, 6, 3)
        D.set_rgb(ctx, L.ACCENT)
        ctx.fill()

    def _draw_notehead(self, ctx, nx, ny, n: Note, color, music_font, glow=False) -> None:
        step = n.staff_step
        # Ledger lines.
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(2.2)
        for s in range(0, step + 1, 2) if step <= 0 else ():
            ctx.move_to(nx - 15, self.staff_y(s))
            ctx.line_to(nx + 15, self.staff_y(s))
        for s in range(12, step + 1, 2):
            ctx.move_to(nx - 15, self.staff_y(s))
            ctx.line_to(nx + 15, self.staff_y(s))
        ctx.stroke()
        if step <= 0:
            for s in range(0, step - 1, -2):
                ctx.move_to(nx - 15, self.staff_y(s))
                ctx.line_to(nx + 15, self.staff_y(s))
            ctx.stroke()
        if glow:
            ctx.arc(nx, ny, 20, 0, 2 * math.pi)
            D.set_rgb(ctx, L.STAR, 0.9)
            ctx.fill()
        hollow = n.note_type in ("half", "whole")
        ctx.save()
        ctx.translate(nx, ny)
        ctx.rotate(-0.35)
        ctx.scale(1.0, 0.72)
        ctx.arc(0, 0, 9.5, 0, 2 * math.pi)
        ctx.restore()
        if hollow:
            D.set_rgb(ctx, color)
            ctx.set_line_width(3.5)
            ctx.stroke()
        else:
            D.set_rgb(ctx, color)
            ctx.fill()
        if n.note_type != "whole":
            up = step < 6
            D.set_rgb(ctx, color)
            ctx.set_line_width(2.4)
            sx_ = nx + 8.5 if up else nx - 8.5
            ctx.move_to(sx_, ny)
            tip = ny - 48 if up else ny + 48
            ctx.line_to(sx_, tip)
            ctx.stroke()
            flags = {"eighth": 1, "16th": 2, "32nd": 3}.get(n.note_type or "", 0)
            for i in range(flags):
                fy = tip + (i * 10 if up else -i * 10)
                ctx.move_to(sx_, fy)
                d = 1 if up else -1
                ctx.curve_to(sx_ + 4, fy + 10 * d, sx_ + 16, fy + 14 * d, sx_ + 10, fy + 28 * d)
                ctx.set_line_width(3)
                ctx.stroke()
        for i in range(n.dots):
            ctx.arc(nx + 16 + i * 8, ny - (3 if step % 2 == 0 else 0), 2.6, 0, 2 * math.pi)
            D.set_rgb(ctx, color)
            ctx.fill()
        if n.accidental:
            glyph = {"sharp": "♯", "flat": "♭", "natural": "♮",
                     "double-sharp": "\U0001D12A", "flat-flat": "\U0001D12B"}.get(n.accidental)
            if glyph:
                D.text(ctx, glyph, nx - 30, ny + 8, 26, color=color, font=music_font, bold=False)

    # highway -----------------------------------------------------------------

    def hw_project(self, lane_x: float, dt: float) -> tuple[float, float, float]:
        """Map (lane x at the strike line, seconds ahead) -> (x, y, scale)."""
        k = 1.7
        z = max(0.0, dt) / self.lookahead
        p = 1 / (1 + k * z)
        p_far = 1 / (1 + k)
        q = (1 - p) / (1 - p_far)
        scale = 1 - (1 - L.HIGHWAY_FAR_SCALE) * q
        y = L.STRIKE_Y - (L.STRIKE_Y - L.HIGHWAY_TOP) * q
        x = L.HIGHWAY_CX + (lane_x - L.HIGHWAY_CX) * scale
        return x, y, scale

    def _highway_outline(self, ctx) -> None:
        lx = L.LANE_X["LT"] - L.HIGHWAY_PAD
        rx = L.LANE_X["R4"] + L.HIGHWAY_PAD
        a = self.hw_project(lx, self.lookahead)
        b = self.hw_project(rx, self.lookahead)
        ctx.new_path()
        ctx.move_to(a[0], a[1])
        ctx.line_to(b[0], b[1])
        ctx.line_to(rx, L.STRIKE_Y + 16)
        ctx.line_to(lx, L.STRIKE_Y + 16)
        ctx.close_path()

    def _draw_highway_static(self, ctx) -> None:
        self._highway_outline(ctx)
        D.fill_ink(ctx, L.HIGHWAY, 6)
        for f in FINGERS:
            lx = L.LANE_X[f]
            hw = L.LANE_W / 2
            a = self.hw_project(lx - hw, self.lookahead)
            b = self.hw_project(lx + hw, self.lookahead)
            ctx.move_to(a[0], a[1])
            ctx.line_to(b[0], b[1])
            ctx.line_to(lx + hw, L.STRIKE_Y)
            ctx.line_to(lx - hw, L.STRIKE_Y)
            ctx.close_path()
            D.set_rgb(ctx, L.HIGHWAY_LANE)
            ctx.fill()
            # Thin coloured guide down the middle of each lane.
            c = L.FINGER_COLORS[f]
            a = self.hw_project(lx, self.lookahead)
            ctx.move_to(a[0], a[1])
            ctx.line_to(lx, L.STRIKE_Y)
            D.set_rgb(ctx, c, 0.35)
            ctx.set_line_width(2)
            ctx.stroke()
        # Lane captions at the far end.
        _, text_font, _ = D.fonts()
        for f, cap in zip(FINGERS, ["thumb", "1", "2", "3", "pinky", "1", "2", "3", "pinky"]):
            x, y, s = self.hw_project(L.LANE_X[f], self.lookahead)
            D.text(ctx, cap, x, y - 8, 15, color=L.FINGER_COLORS[f], align="center", font=text_font)
        x, y, _ = self.hw_project((L.LANE_X["L1"] + L.LANE_X["L3"]) / 2, self.lookahead)
        D.text(ctx, "LEFT HAND", x, y - 28, 18, color=L.WHITE, align="center",
               font=D.fonts()[0], outline=4)
        x, y, _ = self.hw_project((L.LANE_X["R1"] + L.LANE_X["R3"]) / 2, self.lookahead)
        D.text(ctx, "RIGHT HAND", x, y - 28, 18, color=L.WHITE, align="center",
               font=D.fonts()[0], outline=4)

    def _draw_highway(self, ctx, t: float, cur: Event | None) -> None:
        m = self.music_time(t)
        ctx.save()
        self._highway_outline(ctx)
        ctx.clip()

        # Beat and bar lines scrolling toward the strike line.
        lx = L.LANE_X["LT"] - L.HIGHWAY_PAD
        rx = L.LANE_X["R4"] + L.HIGHWAY_PAD
        bar_starts = {float(ms.start_beat) for ms in self.score.measures}
        b0 = math.floor(self.beat_at(max(0.0, m)))
        b1 = self.beat_at(max(0.0, m + self.lookahead)) + 1
        b = b0
        while b <= b1 and b <= float(self.score.total_beats):
            sec = self.score.tempo.seconds(Fraction(b).limit_denominator(64))
            dt = sec - m
            if 0 <= dt <= self.lookahead:
                a = self.hw_project(lx, dt)
                c = self.hw_project(rx, dt)
                is_bar = float(b) in bar_starts
                ctx.move_to(a[0], a[1])
                ctx.line_to(c[0], c[1])
                D.set_rgb(ctx, L.WHITE, 0.45 if is_bar else 0.12)
                ctx.set_line_width((4 if is_bar else 2) * a[2])
                ctx.stroke()
            b += 1

        # Note gems, far ones first so near ones overlap them.
        visible = [ev for ev in self.events if ev.end > t and ev.start < t + self.lookahead]
        for ev in reversed(visible):
            self._draw_gem_row(ctx, t, ev)
        ctx.restore()

        # Strike line and targets.
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(9)
        ctx.move_to(lx + 4, L.STRIKE_Y)
        ctx.line_to(rx - 4, L.STRIKE_Y)
        ctx.stroke()
        D.set_rgb(ctx, L.WHITE)
        ctx.set_line_width(3)
        ctx.move_to(lx + 4, L.STRIKE_Y)
        ctx.line_to(rx - 4, L.STRIKE_Y)
        ctx.stroke()
        active = cur.by_finger if cur else {}
        for f in FINGERS:
            x = L.LANE_X[f]
            c = L.FINGER_COLORS[f]
            on = f in active
            if on:
                age = t - cur.start
                pulse = 1 + 0.25 * max(0.0, 1 - age / IMPACT_TIME)
                for r, a in ((46, 0.18), (36, 0.3)):
                    ctx.save()
                    ctx.translate(x, L.STRIKE_Y)
                    ctx.scale(1, 0.5)
                    ctx.arc(0, 0, r * pulse, 0, 2 * math.pi)
                    ctx.restore()
                    D.set_rgb(ctx, c, a)
                    ctx.fill()
            ctx.save()
            ctx.translate(x, L.STRIKE_Y)
            ctx.scale(1, 0.48)
            ctx.arc(0, 0, 28, 0, 2 * math.pi)
            ctx.restore()
            D.fill_ink(ctx, c if on else D.darken(c, 0.55), 5)
            ctx.save()
            ctx.translate(x, L.STRIKE_Y - 3)
            ctx.scale(1, 0.4)
            ctx.arc(0, 0, 14, 0, 2 * math.pi)
            ctx.restore()
            D.set_rgb(ctx, L.WHITE, 0.9 if on else 0.25)
            ctx.fill()

    def _gem_label(self, finger: str, keys: list[str]) -> str:
        labels = [L.SHORT_LABELS[k] for k in keys if KEYS[k].kind == "key"]
        if finger == "LT":
            return "+".join(["T"] * ("T" in keys) + ["R"] * ("REG" in keys))
        return "+".join(labels)

    def _draw_gem_row(self, ctx, t: float, ev: Event) -> None:
        dt0 = ev.start - t
        dur = ev.end - ev.start
        gap = min(0.07, dur * 0.25)
        dt1 = ev.end - gap - t
        if dt1 <= 0:
            return
        head_visible = dt0 >= -0.02
        lanes = ev.by_finger.items() if ev.fingering is not None else []
        for f, keys in lanes:
            lx = L.LANE_X[f]
            c = L.FINGER_COLORS[f]
            # Sustain tail.
            s0 = max(dt0, 0.0)
            s1 = min(dt1, self.lookahead)
            if s1 > s0:
                tw = L.LANE_W * 0.28
                a, b = self.hw_project(lx - tw, s0), self.hw_project(lx + tw, s0)
                c2, d = self.hw_project(lx + tw, s1), self.hw_project(lx - tw, s1)
                ctx.move_to(a[0], a[1])
                ctx.line_to(b[0], b[1])
                ctx.line_to(c2[0], c2[1])
                ctx.line_to(d[0], d[1])
                ctx.close_path()
                D.fill_ink(ctx, D.lighten(c, 0.15) if dt0 > 0 else D.lighten(c, 0.45), 3)
            if head_visible and dt0 <= self.lookahead:
                x, y, s = self.hw_project(lx, max(dt0, 0.0))
                gw, gh = L.LANE_W * 0.92 * s, 30 * s
                D.rounded_rect(ctx, x - gw / 2, y - gh / 2, gw, gh, gh / 2.4)
                D.fill_ink(ctx, c, 4 * s + 1)
                D.rounded_rect(ctx, x - gw / 2 + 6 * s, y - gh / 2 + 4 * s, gw - 12 * s, gh * 0.28, gh * 0.14)
                D.set_rgb(ctx, L.WHITE, 0.75)
                ctx.fill()
                label = self._gem_label(f, keys)
                if label:
                    D.text(ctx, label, x, y + 8 * s, 21 * s, color=L.WHITE, align="center",
                           font=D.fonts()[0], outline=4 * s)
        if head_visible and dt0 <= self.lookahead:
            # Note name tag at the left edge of the row.
            x, y, s = self.hw_project(L.LANE_X["LT"] - L.HIGHWAY_PAD + 6, max(dt0, 0.0))
            name = ev.note.name if ev.fingering is not None else ev.note.name + "?"
            ctx.select_font_face(D.fonts()[0], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(22 * s)
            tw = ctx.text_extents(name).x_advance + 14 * s
            D.rounded_rect(ctx, x - tw - 6 * s, y - 14 * s, tw, 28 * s, 6 * s)
            D.fill_ink(ctx, L.STAR, 3 * s)
            D.text(ctx, name, x - tw / 2 - 6 * s, y + 8 * s, 22 * s, align="center", font=D.fonts()[0])

    # clarinet ----------------------------------------------------------------

    def _draw_clarinet_body(self, ctx) -> None:
        y, r = L.BODY_Y, L.BODY_R
        # Bell (flared).
        x0, x1 = L.BELL
        ctx.new_path()
        ctx.move_to(x0, y - r)
        ctx.curve_to(x0 + 150, y - r, x1 - 60, y - r - 10, x1, y - r - 66)
        ctx.line_to(x1, y + r + 66)
        ctx.curve_to(x1 - 60, y + r + 10, x0 + 150, y + r, x0, y + r)
        ctx.close_path()
        D.fill_ink(ctx, L.WOOD, 6)
        ctx.new_path()
        ctx.move_to(x0 + 20, y - r + 9)
        ctx.curve_to(x0 + 160, y - r + 9, x1 - 70, y - r - 2, x1 - 6, y - r - 50)
        D.set_rgb(ctx, L.WOOD_LIGHT)
        ctx.set_line_width(7)
        ctx.stroke()
        ctx.save()
        ctx.translate(x1, y)
        ctx.scale(0.22, 1)
        ctx.arc(0, 0, r + 66, 0, 2 * math.pi)
        ctx.restore()
        D.fill_ink(ctx, L.WOOD_DARK, 5)
        self._ring(ctx, x0 - 8, 22, r + 3)
        self._ring(ctx, x1 - 18, 14, r + 60, taper=True)

        # Joints.
        for (a, b) in (L.LOWER_JOINT, L.UPPER_JOINT):
            D.rounded_rect(ctx, a, y - r, b - a, 2 * r, 6)
            D.fill_ink(ctx, L.WOOD, 6)
            D.set_rgb(ctx, L.WOOD_LIGHT)
            ctx.rectangle(a + 8, y - r + 8, b - a - 16, 7)
            ctx.fill()
            D.set_rgb(ctx, L.WHITE, 0.55)
            ctx.rectangle(a + 14, y - r + 10, b - a - 28, 2)
            ctx.fill()
            D.set_rgb(ctx, L.WOOD_DARK)
            ctx.rectangle(a + 6, y + r - 12, b - a - 12, 7)
            ctx.fill()
        # Barrel (slight bulge).
        a, b = L.BARREL
        ctx.new_path()
        ctx.move_to(a, y - r + 2)
        ctx.curve_to(a + 30, y - r - 6, b - 30, y - r - 6, b, y - r + 2)
        ctx.line_to(b, y + r - 2)
        ctx.curve_to(b - 30, y + r + 6, a + 30, y + r + 6, a, y + r - 2)
        ctx.close_path()
        D.fill_ink(ctx, L.WOOD, 6)
        D.set_rgb(ctx, L.WOOD_LIGHT)
        ctx.rectangle(a + 10, y - r + 6, b - a - 20, 6)
        ctx.fill()
        for rx in (L.BARREL[0], L.BARREL[1], L.UPPER_JOINT[1], L.LOWER_JOINT[1] - 6):
            self._ring(ctx, rx - 7, 14, r + 3)

        # Mouthpiece, ligature and reed.
        a, b = L.MOUTHPIECE
        ctx.new_path()
        ctx.move_to(b, y - r + 4)
        ctx.line_to(a + 70, y - r + 8)
        ctx.curve_to(a + 20, y - 14, a, y - 6, a, y + 4)
        ctx.line_to(a + 6, y + r - 8)
        ctx.line_to(b, y + r - 4)
        ctx.close_path()
        D.fill_ink(ctx, D.darken(L.WOOD, 0.3), 6)
        D.set_rgb(ctx, L.WOOD_LIGHT)
        ctx.set_line_width(5)
        ctx.move_to(a + 70, y - r + 15)
        ctx.line_to(b - 10, y - r + 12)
        ctx.stroke()
        # Reed underneath.
        ctx.new_path()
        ctx.move_to(a + 4, y + r - 6)
        ctx.line_to(b - 40, y + r - 2)
        ctx.line_to(b - 40, y + r + 7)
        ctx.line_to(a + 10, y + r + 1)
        ctx.close_path()
        D.fill_ink(ctx, L.REED, 4)
        lig = (a + 108, a + 152)
        D.rounded_rect(ctx, lig[0], y - r + 2, lig[1] - lig[0], 2 * r + 8, 6)
        D.fill_ink(ctx, L.SILVER, 5)
        D.set_rgb(ctx, L.SILVER_SHADE)
        ctx.rectangle(lig[0] + 4, y + 8, lig[1] - lig[0] - 8, r - 6)
        ctx.fill()
        ctx.arc(lig[1] - 10, y + r + 12, 7, 0, 2 * math.pi)
        D.fill_ink(ctx, L.SILVER, 4)

        # Thumb rest on the back of the lower joint (dashed = behind).
        ctx.save()
        ctx.set_dash([7, 6])
        D.rounded_rect(ctx, 1206, y - 14, 40, 28, 8)
        D.set_rgb(ctx, L.SILVER, 0.6)
        ctx.fill_preserve()
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(3)
        ctx.stroke()
        ctx.restore()

        # Rods linking the keys (decorative).
        D.set_rgb(ctx, L.SILVER)
        ctx.set_line_width(4)
        for x0_, x1_ in ((585, 930), (1040, 1400)):
            ctx.move_to(x0_, y - r - 1)
            ctx.line_to(x1_, y - r - 1)
        ctx.stroke()
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(1.5)
        for x0_, x1_ in ((585, 930), (1040, 1400)):
            ctx.move_to(x0_, y - r - 3.5)
            ctx.line_to(x1_, y - r - 3.5)
        ctx.stroke()

    def _ring(self, ctx, x, w, r, taper=False) -> None:
        y = L.BODY_Y
        D.rounded_rect(ctx, x, y - r, w, 2 * r, 3)
        D.fill_ink(ctx, L.SILVER, 4)
        D.set_rgb(ctx, L.SILVER_SHADE)
        ctx.rectangle(x + 3, y + r * 0.35, w - 6, r * 0.55)
        ctx.fill()
        D.set_rgb(ctx, L.SILVER_LIGHT)
        ctx.rectangle(x + 3, y - r + 5, w - 6, 4)
        ctx.fill()

    def _key_shape(self, ctx, key: str) -> None:
        """Add the outline of a key/hole to the current path."""
        x, y, kind = L.KEY_POS[key]
        if kind == "hole":
            ctx.arc(x, y, 17, 0, 2 * math.pi)
        elif kind == "back_hole":
            ctx.arc(x, y, 15, 0, 2 * math.pi)
        elif kind == "back_key":
            D.rounded_rect(ctx, x - 20, y - 10, 40, 20, 9)
        elif kind == "top_lever":
            D.rounded_rect(ctx, x - 19, y - 10, 38, 18, 8)
        elif kind == "side":
            D.rounded_rect(ctx, x - 11, y - 9, 22, 16, 6)
        elif kind == "spatula":
            D.rounded_rect(ctx, x - 19, y - 11, 38, 22, 9)

    def _draw_keys(self, ctx, t: float, cur: Event | None, nxt: Event | None) -> None:
        pressed = cur.fingering or frozenset() if cur else frozenset()
        upcoming = frozenset()
        u_amt = 0.0
        if nxt is not None and nxt.fingering is not None:
            lead = nxt.start - t
            if lead <= UPCOMING_WINDOW:
                upcoming = nxt.fingering
                u_amt = 1 - lead / UPCOMING_WINDOW
        _, text_font, _ = D.fonts()
        for key, (x, y, kind) in L.KEY_POS.items():
            finger = KEYS[key].finger
            col = L.FINGER_COLORS[finger]
            on = key in pressed
            # Stalk connecting levers to the body.
            if kind == "spatula":
                D.set_rgb(ctx, L.INK)
                ctx.set_line_width(9)
                ctx.move_to(x, L.BODY_BOTTOM - 4)
                ctx.line_to(x, y)
                ctx.stroke()
                D.set_rgb(ctx, L.SILVER)
                ctx.set_line_width(4)
                ctx.move_to(x, L.BODY_BOTTOM - 4)
                ctx.line_to(x, y)
                ctx.stroke()
            if key in upcoming and not (on and key in upcoming and u_amt < 0.01):
                # Pulsing halo for keys needed by the next note.
                pulse = 0.5 + 0.5 * math.sin(t * 18)
                ctx.save()
                self._halo_path(ctx, key, 9 + 6 * u_amt)
                D.set_rgb(ctx, col, 0.25 + 0.55 * u_amt * (0.6 + 0.4 * pulse))
                ctx.set_line_width(6 + 4 * u_amt)
                ctx.stroke()
                ctx.restore()
            if on:
                ctx.save()
                self._halo_path(ctx, key, 12)
                D.set_rgb(ctx, col, 0.45)
                ctx.fill()
                ctx.restore()
            back = kind.startswith("back")
            if kind == "hole":
                ctx.arc(x, y, 17, 0, 2 * math.pi)
                D.fill_ink(ctx, col if on else L.SILVER, 4)
                ctx.arc(x, y, 10, 0, 2 * math.pi)
                D.fill_ink(ctx, D.darken(col, 0.35) if on else L.WOOD_DARK, 3)
            else:
                ctx.save()
                if back:
                    ctx.set_dash([6, 5])
                self._key_shape(ctx, key)
                fill = col if on else (L.SILVER if not back else D.mix(L.SILVER, L.WOOD, 0.5))
                D.set_rgb(ctx, fill)
                ctx.fill_preserve()
                D.set_rgb(ctx, L.INK)
                ctx.set_line_width(4 if not back else 3)
                ctx.stroke()
                ctx.restore()
                if not on and not back:
                    D.set_rgb(ctx, L.SILVER_SHADE)
                    ctx.rectangle(x - 10, y + 1, 20, 4)
                    ctx.fill()
                label = L.SHORT_LABELS.get(key, "")
                if label:
                    D.text(ctx, label, x, y + 6, 14 if kind != "side" else 11,
                           color=L.WHITE if (on or back) else L.INK, align="center", font=text_font)
            if on and cur is not None:
                age = t - cur.start
                if 0 <= age < IMPACT_TIME:
                    self._impact(ctx, x, y, col, age / IMPACT_TIME)
        # Captions for the parts that are on the back of the instrument.
        D.text(ctx, "thumb keys (back)", 430, L.BODY_BOTTOM + 22, 14, align="center",
               color=D.lighten(L.INK, 0.25), font=text_font)

    def _halo_path(self, ctx, key: str, grow: float) -> None:
        x, y, kind = L.KEY_POS[key]
        if kind in ("hole", "back_hole"):
            ctx.arc(x, y, 17 + grow, 0, 2 * math.pi)
        else:
            sizes = {"back_key": (40, 20), "top_lever": (38, 18), "side": (22, 16), "spatula": (38, 22)}
            w, h = sizes[kind]
            D.rounded_rect(ctx, x - w / 2 - grow, y - h / 2 - grow, w + 2 * grow, h + 2 * grow, 8 + grow)

    def _impact(self, ctx, x, y, col, u: float) -> None:
        """Comic 'pow' lines bursting out when a key is pressed."""
        r0 = 26 + 18 * u
        r1 = r0 + 16 * (1 - u)
        ctx.save()
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for i in range(8):
            a = i * math.pi / 4 + 0.3
            ctx.move_to(x + r0 * math.cos(a), y + r0 * math.sin(a))
            ctx.line_to(x + r1 * math.cos(a), y + r1 * math.sin(a))
        D.set_rgb(ctx, L.INK, 1 - u)
        ctx.set_line_width(6)
        ctx.stroke_preserve()
        D.set_rgb(ctx, col, 1 - u)
        ctx.set_line_width(3)
        ctx.stroke()
        ctx.restore()

    # hands -------------------------------------------------------------------

    def _draw_finger(self, ctx, finger: str, tip, pressed: float, ghost=False) -> None:
        """A finger is a fat curved tube from knuckle to tip. Lifted fingers
        come toward the viewer, so they read shorter (foreshortened)."""
        base = L.KNUCKLES[finger]
        w = L.FINGER_W[finger]
        dx, dy = tip[0] - base[0], tip[1] - base[1]
        ln = math.hypot(dx, dy) or 1
        ux, uy = dx / ln, dy / ln
        # Bow the finger slightly away from the middle of its hand.
        side = -1 if finger in ("L1", "LT", "R1") else (1 if finger[1] in "34" else 0.3)
        bow = 0.1 * ln * side
        ctrl = ((base[0] + tip[0]) / 2 - uy * bow, (base[1] + tip[1]) / 2 + ux * bow)
        c1 = (base[0] + (ctrl[0] - base[0]) * 2 / 3, base[1] + (ctrl[1] - base[1]) * 2 / 3)
        c2 = (tip[0] + (ctrl[0] - tip[0]) * 2 / 3, tip[1] + (ctrl[1] - tip[1]) * 2 / 3)

        def bez(u: float):
            a = (1 - u) ** 3, 3 * (1 - u) ** 2 * u, 3 * (1 - u) * u * u, u ** 3
            return (a[0] * base[0] + a[1] * c1[0] + a[2] * c2[0] + a[3] * tip[0],
                    a[0] * base[1] + a[1] * c1[1] + a[2] * c2[1] + a[3] * tip[1])

        def path():
            ctx.new_path()
            ctx.move_to(*base)
            ctx.curve_to(*c1, *c2, *tip)

        if ghost:
            ctx.push_group()
        ctx.save()
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        path()
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(w + 9)
        ctx.stroke()
        path()
        D.set_rgb(ctx, L.SKIN)
        ctx.set_line_width(w)
        ctx.stroke()
        # Cel shading down one side, and a highlight down the other.
        ctx.save()
        ctx.translate(uy * w * 0.24, -ux * w * 0.24)
        path()
        D.set_rgb(ctx, L.SKIN_SHADE, 0.85)
        ctx.set_line_width(w * 0.28)
        ctx.stroke()
        ctx.restore()
        ctx.save()
        ctx.translate(-uy * w * 0.2, ux * w * 0.2)
        path()
        D.set_rgb(ctx, L.SKIN_LIGHT, 0.9)
        ctx.set_line_width(w * 0.12)
        ctx.stroke()
        ctx.restore()
        ctx.restore()
        # Pressed fingertips squash a little wider onto the key.
        if pressed > 0.01:
            ctx.arc(tip[0], tip[1], w * (0.5 + 0.08 * pressed), 0, 2 * math.pi)
            D.set_rgb(ctx, L.SKIN)
            ctx.fill()
        # Knuckle creases.
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(2.6)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for u_at, span in ((0.38, 0.32), (0.66, 0.24)):
            px, py = bez(u_at)
            ctx.move_to(px + uy * w * span, py - ux * w * span)
            ctx.line_to(px - uy * w * span * 0.2, py + ux * w * span * 0.2)
        ctx.stroke()
        # Fingernail near the tip.
        nail_c = (tip[0] - ux * w * 0.36, tip[1] - uy * w * 0.36)
        ctx.save()
        ctx.translate(*nail_c)
        ctx.rotate(math.atan2(uy, ux))
        D.rounded_rect(ctx, -w * 0.3, -w * 0.25, w * 0.58, w * 0.5, w * 0.2)
        ctx.restore()
        D.fill_ink(ctx, D.mix(L.SKIN_LIGHT, (1.0, 0.82, 0.82), 0.4), 2.5)
        if ghost:
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(0.55)

    def _draw_palm(self, ctx, hand: str) -> None:
        cfg = L.PALMS[hand]
        wx, wy = cfg["wrist"]
        half = cfg["width"] / 2
        fingers = [f"{hand}{i}" for i in (1, 2, 3, 4)]
        ks = [L.KNUCKLES[f] for f in fingers]
        # Sleeve.
        ctx.new_path()
        ctx.move_to(wx - half + 18, wy - 30)
        ctx.line_to(wx + half - 18, wy - 30)
        ctx.line_to(wx + half + 30, L.H + 10)
        ctx.line_to(wx - half - 30, L.H + 10)
        ctx.close_path()
        D.fill_ink(ctx, L.SLEEVE, 6)
        D.set_rgb(ctx, L.SLEEVE_SHADE)
        ctx.move_to(wx + 20, wy)
        ctx.line_to(wx + half - 10, wy)
        ctx.line_to(wx + half + 30, L.H)
        ctx.line_to(wx + 40, L.H)
        ctx.close_path()
        ctx.fill()
        # Back of the hand.
        ctx.new_path()
        ctx.move_to(wx - half + 30, wy - 24)
        if hand == "L":
            ctx.curve_to(wx - half - 10, wy - 120, ks[0][0] - 60, ks[0][1] + 30, ks[0][0] - 18, ks[0][1] - 4)
        else:
            ctx.curve_to(wx - half, wy - 120, ks[0][0] - 50, ks[0][1] + 30, ks[0][0] - 18, ks[0][1] - 4)
        for i in range(len(ks) - 1):
            a, b = ks[i], ks[i + 1]
            ctx.curve_to(a[0] + 10, a[1] - 22, b[0] - 10, b[1] - 22, b[0], b[1] - 6)
        last = ks[-1]
        ctx.curve_to(last[0] + 30, last[1] + 10, wx + half + 20, wy - 110, wx + half - 30, wy - 24)
        ctx.close_path()
        D.fill_ink(ctx, L.SKIN, 6)
        # Cel shade and knuckle marks.
        ctx.new_path()
        ctx.move_to(wx - half + 40, wy - 34)
        ctx.curve_to(wx - 40, wy - 70, wx + 60, wy - 70, wx + half - 40, wy - 34)
        ctx.line_to(wx + half - 34, wy - 26)
        ctx.line_to(wx - half + 34, wy - 26)
        ctx.close_path()
        D.set_rgb(ctx, L.SKIN_SHADE, 0.7)
        ctx.fill()
        D.set_rgb(ctx, L.INK)
        ctx.set_line_width(3)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        for k in ks[:3]:
            ctx.arc(k[0], k[1] + 26, 9, math.pi * 1.15, math.pi * 1.85)
            ctx.new_sub_path()
        ctx.stroke()
        # Cuff.
        D.rounded_rect(ctx, wx - half + 6, wy - 34, cfg["width"] - 12, 34, 8)
        D.fill_ink(ctx, L.CUFF, 5)

    def _draw_hands(self, ctx, t: float) -> None:
        # Right-hand thumb sits behind the instrument under the thumb rest.
        self._draw_thumb_static(ctx)
        for hand in ("L", "R"):
            order = [f"{hand}4", f"{hand}3", f"{hand}2", f"{hand}1"]
            if hand == "L":
                tip, pr = self.finger_tip("LT", t)
                self._draw_finger(ctx, "LT", tip, pr, ghost=True)
            for f in order:
                tip, pr = self.finger_tip(f, t)
                self._draw_finger(ctx, f, tip, pr)
            self._draw_palm(ctx, hand)

    def _draw_thumb_static(self, ctx) -> None:
        base, tip = L.RH_THUMB["base"], L.RH_THUMB["tip"]
        ctx.push_group()
        D.capsule_stroke(ctx, [base, ((base[0] + tip[0]) / 2 - 18, (base[1] + tip[1]) / 2 + 10), tip],
                         36, L.SKIN, ink_w=4.5)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(0.5)

    # panels --------------------------------------------------------------------

    def _caption(self, ctx, x, y, s: str, fill=L.STAR) -> None:
        title_font = D.fonts()[0]
        ctx.select_font_face(title_font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(24)
        w = ctx.text_extents(s).x_advance + 26
        ctx.save()
        ctx.translate(x, y)
        ctx.rotate(-0.03)
        D.rounded_rect(ctx, 0, 0, w, 36, 3)
        D.fill_ink(ctx, fill, 4)
        D.text(ctx, s, 13, 27, 24, font=title_font)
        ctx.restore()

    def _draw_info(self, ctx, t: float, cur: Event | None, nxt: Event | None) -> None:
        x, y, w, h = L.INFO_PANEL
        title_font, text_font, _ = D.fonts()
        self._caption(ctx, x - 10, y - 18, "NOW PLAYING")
        cx, cy = x + w / 2, y + 128
        if t < self.lead_in and self.events:
            remaining = self.events[0].start - t
            label, sub, col = "READY?", f"starts in {remaining:0.1f}s", L.STAR
        elif cur is None:
            label, sub, col = ("REST", "breathe!", (0.85, 0.88, 0.95)) if nxt else ("FIN!", "nice playing", L.STAR)
        else:
            label = cur.note.name
            sub = f"sounds {cur.note.concert_name} (concert)" if self.show_concert else ""
            col = L.STAR
        age = (t - cur.start) if cur else 1.0
        pop = 1 + 0.12 * max(0.0, 1 - age / 0.15)
        D.starburst(ctx, cx, cy, 112 * pop, 84 * pop, points=16, rot=t * 0.15,
                    jitter=[1.0, 1.0, 0.94, 1.0, 1.06, 1.0, 0.97, 1.0])
        D.fill_ink(ctx, col, 6)
        D.starburst(ctx, cx, cy, 94 * pop, 72 * pop, points=16, rot=t * 0.15)
        D.set_rgb(ctx, L.STAR_EDGE if label not in ("REST",) else (0.55, 0.6, 0.75), 0.9)
        ctx.set_line_width(3)
        ctx.stroke()
        size = 74 if len(label) <= 2 else (62 if len(label) == 3 else 52)
        D.text(ctx, label, cx, cy + size * 0.36, size * pop, color=L.WHITE, align="center",
               font=title_font, outline=10)
        D.text(ctx, sub, cx, y + 272, 20, align="center", font=text_font)
        if cur is not None:
            reg = register_name(cur.note.written_midi)
            D.text(ctx, reg.upper(), cx, y + 300, 18, align="center", color=L.ACCENT, font=title_font)
            self._mini_fingering(ctx, cx, y + 326, cur)
        elif nxt is not None and t >= self.lead_in:
            D.text(ctx, f"next: {nxt.note.name}", cx, y + 310, 20, align="center", font=text_font)

    def _mini_fingering(self, ctx, cx, cy, ev: Event) -> None:
        """Tiny fingering diagram: T | 1 2 3 | 1 2 3 plus extra keys."""
        fing = ev.fingering
        if fing is None:
            D.text(ctx, "no standard fingering", cx, cy + 6, 16, align="center")
            return
        holes = ["T", "L1", "L2", "L3", None, "R1", "R2", "R3"]
        x = cx - 150
        for k in holes:
            if k is None:
                D.set_rgb(ctx, L.INK)
                ctx.set_line_width(3)
                ctx.move_to(x, cy - 12)
                ctx.line_to(x, cy + 12)
                ctx.stroke()
                x += 14
                continue
            ctx.arc(x + 9, cy, 9, 0, 2 * math.pi)
            on = k in fing
            D.fill_ink(ctx, L.FINGER_COLORS[KEYS[k].finger] if on else L.WHITE, 3)
            x += 24
            if k == "T":
                x += 6
        extras = [L.SHORT_LABELS[k] if k != "REG" else "Reg" for k in sorted(fing)
                  if KEYS[k].kind == "key"]
        if extras:
            D.text(ctx, "+ " + ", ".join(extras), x + 4, cy + 7, 17, font=D.fonts()[1])

    def _draw_next(self, ctx, t: float, nxt_i: int) -> None:
        x, y, w, h = L.NEXT_PANEL
        title_font, text_font, _ = D.fonts()
        self._caption(ctx, x - 10, y - 18, "COMING UP", fill=L.FINGER_COLORS["L1"])
        upcoming = self.events[nxt_i:nxt_i + 5]
        yy = y + 52
        for i, ev in enumerate(upcoming):
            lead = ev.start - t
            beat_len = 60 / self.score.tempo.bpm_at(Fraction(0))
            size = 34 if i == 0 else 26
            D.text(ctx, ev.note.name, x + 26, yy + size * 0.8, size, font=title_font,
                   color=L.ACCENT if i == 0 else L.INK)
            D.text(ctx, f"in {lead / beat_len:0.1f} beats", x + w - 22, yy + size * 0.8, 17,
                   align="right", font=text_font, color=D.lighten(L.INK, 0.3))
            yy += size + 18
        m = self.music_time(t)
        bar = "-"
        for meas in self.score.measures:
            if meas.start <= max(m, 0):
                bar = meas.number
        bpm = self.score.tempo.bpm_at(Fraction(self.beat_at(max(m, 0.0))).limit_denominator(64))
        D.text(ctx, f"bar {bar}   •   {bpm:.0f} bpm", x + w / 2, y + h - 22, 20, align="center",
               font=text_font)
