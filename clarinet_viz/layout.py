"""Scene geometry and colours. Everything is laid out on a 1920x1080 canvas
and scaled to the output size.

The clarinet is shown on the left as a fingering chart: tone holes as
circles and keys as ovals, laid out like a printed chart, top to bottom.
Each finger has a horizontal lane at the height of the keys it plays; notes
scroll in from the right toward a strike line beside the chart. The staff along the top shares the highway's timeline, so a
note on the staff sits directly above its gems.
"""

from __future__ import annotations

W, H = 1920, 1080

# --- colours -------------------------------------------------------------


def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


INK = hex_rgb("#141218")
WHITE = (1.0, 1.0, 1.0)
BG_TOP = hex_rgb("#141226")
BG_BOTTOM = hex_rgb("#08070e")

HIGHWAY = hex_rgb("#191630")
HIGHWAY_LANE = hex_rgb("#231f42")
ACCENT = hex_rgb("#ff2e88")
STAR = hex_rgb("#ffd83a")

# Guitar Hero style colour per finger: same finger, same colour on both hands.
FINGER_COLORS = {
    "LT": hex_rgb("#ff8a00"),
    "L1": hex_rgb("#22c55e"), "R1": hex_rgb("#22c55e"),
    "L2": hex_rgb("#ef2b2d"), "R2": hex_rgb("#ef2b2d"),
    "L3": hex_rgb("#ffd21f"), "R3": hex_rgb("#ffd21f"),
    "L4": hex_rgb("#1e88ff"), "R4": hex_rgb("#1e88ff"),
}
FINGER_LABELS = {
    "LT": "L thumb", "L1": "L index", "L2": "L middle", "L3": "L ring", "L4": "L pinky",
    "R1": "R index", "R2": "R middle", "R3": "R ring", "R4": "R pinky",
}

# --- fingering chart ------------------------------------------------------

# The chart copies a standard teacher's clarinet fingering chart. Positions
# below are in that chart's own units (REF_*), scaled onto the canvas, so
# the shapes keep the original's proportions: a teardrop register key, the
# thumb hole, three holes per hand, the right-hand side keys, and four
# staggered right-pinky keys.
CHART_PANEL = (392, 178, 304, 890)     # x, y, w, h of the white chart card
REF_SCALE = 1.7
REF_COL = 82                           # x of the column of finger holes
_CX, _Y0 = 524, 202                    # where the column / the top land on the canvas


def _x(x):
    return round(_CX + (x - REF_COL) * REF_SCALE)


def _y(y):
    return round(_Y0 + (y - 12) * REF_SCALE)


def _k(x, y, shape, a, b=0, rot=0.0):
    """A key: centre, shape ('circle' radius a; 'oval', 'drop', 'blade' and
    'blade_r' a wide and b tall) and tilt in degrees, all in chart units."""
    return (_x(x), _y(y), shape, round(a * REF_SCALE, 1), round(b * REF_SCALE, 1), rot)


_GAP = 60   # extra room between the left hand's holes and the divider for the left pinky keys

# Keys the fingering table presses.
KEY_SHAPE = {
    "REG": _k(36, 54, "drop", 19, 84),
    "T": _k(36, 122, "circle", 18.5),
    "L1": _k(82, 96, "circle", 18.5),
    "L2": _k(82, 148, "circle", 18.5),
    "L3": _k(82, 199, "circle", 18.5),
    # Not on the reference (it shows no A, G# or left pinky keys), but some
    # fingerings need them: drawn in the same plain style.
    "A": _k(124, 66, "oval", 34, 15),
    "GS": _k(136, 108, "oval", 15, 36),
    "LE": _k(50, 240, "oval", 44, 15, 8),
    "LFS": _k(56, 257, "oval", 44, 15, 8),
    "LCS": _k(50, 274, "oval", 44, 15, 8),
    "R1": _k(82, 274 + _GAP, "circle", 18.5),
    "R2": _k(82, 325 + _GAP, "circle", 18.5),
    "R3": _k(82, 376 + _GAP, "circle", 18.5),
    "S4": _k(120, 343.5, "blade", 18, 65),
    "RE": _k(52.5, 410 + _GAP, "oval", 45, 21, 11),
    "RGS": _k(51, 435 + _GAP, "oval", 45, 22, 11),
    "RF": _k(79, 435 + _GAP, "oval", 49, 24, 12),
}

# Keys the reference shows that no fingering here uses: (finger, shape...).
DECOR = [
    ("R1", *_k(140.5, 348.5, "blade_r", 19, 53)),
    ("R1", *_k(145.5, 310.5, "oval", 31, 17, -8)),
    ("R4", *_k(78, 410 + _GAP, "oval", 49, 24, 12)),
]

DIVIDER_Y = _y(236 + _GAP)             # line between the left and right hands
DIVIDER_HALF = round(17 * REF_SCALE)

SHORT_LABELS = {
    "REG": "Reg", "T": "T", "A": "A", "GS": "G#", "LE": "E", "LFS": "F#", "LCS": "C#",
    "S4": "Eb", "RE": "E", "RF": "F", "RGS": "Ab",
}

ICON_SIZE = 54   # mini key diagram on a highway gem fits this box

# --- highway -------------------------------------------------------------

LANE_Y = {"LT": 270, "L1": KEY_SHAPE["L1"][1], "L2": KEY_SHAPE["L2"][1], "L3": KEY_SHAPE["L3"][1],
          "L4": KEY_SHAPE["LFS"][1], "R1": KEY_SHAPE["R1"][1], "R2": KEY_SHAPE["R2"][1],
          "R3": KEY_SHAPE["R3"][1], "R4": KEY_SHAPE["RF"][1]}
LANE_H = 62
STRIKE_X = 762
HIGHWAY_RECT = (718, 196, 1186, 872)   # x, y, w, h
PX_PER_SEC = 380
GEM_H = 44

# --- staff strip (shares the highway's timeline) ---------------------------

STAFF_PANEL = (470, 12, 1434, 158)
STAFF_NOTES_LEFT = 612                 # notes are hidden under the clef left of this
STAFF_BOTTOM_LINE = 114
STAFF_SPACE = 13
NAME_ROW_Y = 184                       # note-name tags between staff and lanes

NOW_PANEL = (16, 12, 436, 158)
