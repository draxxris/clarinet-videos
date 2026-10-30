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

CHART_X = 560                          # the column of tone holes
CHART_PANEL = (392, 178, 304, 890)     # x, y, w, h of the white chart card
DIVIDER_Y = 562                        # line between the left and right hands
HOLE_R = 30

# Each key as (x, y, shape, a, b): a circle of radius a, or an oval a wide
# and b tall. The arrangement follows a printed clarinet fingering chart.
KEY_SHAPE = {
    "REG": (468, 214, "oval", 22, 66),
    "T": (482, 288, "circle", 24, 0),
    "A": (562, 254, "oval", 50, 20),
    "GS": (620, 268, "oval", 20, 44),
    "L1": (CHART_X, 336, "circle", HOLE_R, 0),
    "L2": (CHART_X, 420, "circle", HOLE_R, 0),
    "L3": (CHART_X, 504, "circle", HOLE_R, 0),
    "LE": (462, 598, "oval", 62, 24),
    "LFS": (474, 626, "oval", 62, 24),
    "LCS": (462, 654, "oval", 62, 24),
    "S1": (624, 606, "oval", 16, 28),
    "S2": (624, 638, "oval", 16, 28),
    "S3": (624, 670, "oval", 16, 28),
    "S4": (656, 712, "oval", 22, 46),
    "R1": (CHART_X, 738, "circle", HOLE_R, 0),
    "R2": (CHART_X, 822, "circle", HOLE_R, 0),
    "R3": (CHART_X, 906, "circle", HOLE_R, 0),
    "RE": (536, 982, "oval", 66, 26),
    "RF": (556, 1010, "oval", 66, 26),
    "RGS": (536, 1038, "oval", 66, 26),
}

SHORT_LABELS = {
    "REG": "Reg", "T": "T", "A": "A", "GS": "G#", "LE": "E", "LFS": "F#", "LCS": "C#",
    "S1": "1", "S2": "2", "S3": "3", "S4": "Eb", "RE": "E", "RF": "F", "RGS": "Ab",
}

# Mini diagrams on the highway gems: each finger's keys in a compact version
# of the chart's arrangement, in a box ICON_SIZE across (same shape tuples,
# relative to the box centre).
ICON_SIZE = 54
ICON_SHAPE = {
    "REG": (-11, -7, "oval", 10, 30),
    "T": (8, 11, "circle", 10, 0),
    "A": (-3, -16, "oval", 24, 10),
    "GS": (17, -10, "oval", 9, 20),
    "L1": (-3, 9, "circle", 13, 0),
    "LE": (-3, -13, "oval", 32, 12),
    "LFS": (4, 0, "oval", 32, 12),
    "LCS": (-3, 13, "oval", 32, 12),
    "S1": (6, -19, "oval", 8, 12),
    "S2": (6, -6, "oval", 8, 12),
    "S3": (6, 7, "oval", 8, 12),
    "S4": (18, 15, "oval", 10, 20),
    "R1": (-12, 11, "circle", 11, 0),
    "RE": (-3, -13, "oval", 34, 12),
    "RF": (4, 0, "oval", 34, 12),
    "RGS": (-3, 13, "oval", 34, 12),
}

# --- highway -------------------------------------------------------------

LANE_Y = {"LT": 250, "L1": 336, "L2": 420, "L3": 504, "L4": 624,
          "R1": 738, "R2": 822, "R3": 906, "R4": 1010}
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
