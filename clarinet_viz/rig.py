"""A rigid 2D hand rig. Each hand moves and rotates as one piece, and its
fingers keep a fixed length: to reach a key the hand shifts, rather than the
finger stretching. A finger's on-screen length only shrinks when it curls up
toward the viewer (lifted off a hole)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import layout as L

HAND_FINGERS = {"L": ["LT", "L1", "L2", "L3", "L4"], "R": ["R1", "R2", "R3", "R4"]}
FINGER_HAND = {f: h for h, fs in HAND_FINGERS.items() for f in fs}


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def base_of(finger: str):
    """Rest-pose position of a finger's base (knuckle, or thumb root)."""
    if finger == "LT":
        return L.HANDS["L"]["thumb_base"]
    return L.KNUCKLES[finger]


FINGER_LEN = {f: _dist(base_of(f), L.KEY_POS[L.HOME[f]][:2]) / L.REACH for f in FINGER_HAND}


@dataclass(frozen=True)
class Pose:
    dx: float = 0.0
    dy: float = 0.0
    theta: float = 0.0

    def blend(self, other: "Pose", u: float) -> "Pose":
        return Pose(self.dx + (other.dx - self.dx) * u, self.dy + (other.dy - self.dy) * u,
                    self.theta + (other.theta - self.theta) * u)


REST = Pose()


def to_world(hand: str, pose: Pose, p):
    px, py = L.HANDS[hand]["pivot"]
    c, s = math.cos(pose.theta), math.sin(pose.theta)
    x, y = p[0] - px, p[1] - py
    return (px + pose.dx + c * x - s * y, py + pose.dy + s * x + c * y)


def to_local(hand: str, pose: Pose, p):
    px, py = L.HANDS[hand]["pivot"]
    c, s = math.cos(pose.theta), math.sin(pose.theta)
    x, y = p[0] - px - pose.dx, p[1] - py - pose.dy
    return (px + c * x + s * y, py - s * x + c * y)


def apply(ctx, hand: str, pose: Pose) -> None:
    """Set up ctx so that drawing in rest-pose coordinates lands in the posed hand."""
    px, py = L.HANDS[hand]["pivot"]
    ctx.translate(px + pose.dx, py + pose.dy)
    ctx.rotate(pose.theta)
    ctx.translate(-px, -py)


def solve_pose(hand: str, targets: dict[str, tuple[float, float]]) -> Pose:
    """Place the hand so each pressing finger reaches its key comfortably.

    targets: finger -> point it must touch. Other fingers stay near their
    home keys. Solved with a few Gauss-Newton steps (3 unknowns)."""
    fingers = HAND_FINGERS[hand]

    def residuals(v):
        pose = Pose(*v)
        out = []
        for f in fingers:
            k = to_world(hand, pose, base_of(f))
            length = FINGER_LEN[f]
            if f in targets:
                d = _dist(k, targets[f])
                out.append((d - L.REACH * length) * 1.0)
                out.append(max(0.0, d - 0.99 * length) * 4.0)  # must not over-reach
            else:
                home = L.KEY_POS[L.HOME[f]][:2]
                out.append((_dist(k, home) - L.REACH * length) * 0.25)
        out += [v[0] * 0.06, v[1] * 0.06, v[2] * 160]
        return np.array(out)

    v = np.zeros(3)
    for _ in range(12):
        r = residuals(v)
        jac = np.empty((len(r), 3))
        for j, step in enumerate((0.5, 0.5, 0.002)):
            dv = np.zeros(3)
            dv[j] = step
            jac[:, j] = (residuals(v + dv) - r) / step
        delta, *_ = np.linalg.lstsq(jac, -r, rcond=None)
        v = v + delta
        if np.linalg.norm(delta) < 1e-3:
            break
    return Pose(*v)


def hover_tip(finger: str, pose: Pose):
    """Where a lifted fingertip appears: curled up, pointing at its home key."""
    hand = FINGER_HAND[finger]
    k = to_world(hand, pose, base_of(finger))
    home = L.KEY_POS[L.HOME[finger]][:2]
    d = _dist(k, home) or 1.0
    reach = FINGER_LEN[finger] * L.CURL
    return (k[0] + (home[0] - k[0]) / d * reach, k[1] + (home[1] - k[1]) / d * reach)


def clamp_tip(finger: str, pose: Pose, tip):
    """Keep a fingertip within the finger's length of its knuckle."""
    hand = FINGER_HAND[finger]
    k = to_world(hand, pose, base_of(finger))
    d = _dist(k, tip)
    length = FINGER_LEN[finger]
    if d <= length:
        return tip
    return (k[0] + (tip[0] - k[0]) * length / d, k[1] + (tip[1] - k[1]) * length / d)
