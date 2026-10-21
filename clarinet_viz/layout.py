"""Scene geometry and colours. Everything is laid out on a 1920x1080 canvas
and scaled to the output size."""

from __future__ import annotations

W, H = 1920, 1080

# --- colours -------------------------------------------------------------

def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


INK = hex_rgb("#111111")
PAPER = hex_rgb("#fff3d1")
PAPER_DOT = hex_rgb("#f6d98f")
WHITE = (1.0, 1.0, 1.0)
SKIN = hex_rgb("#f5c39a")
SKIN_SHADE = hex_rgb("#d9946a")
SKIN_LIGHT = hex_rgb("#ffe0c4")
SLEEVE = hex_rgb("#2d5bd8")
SLEEVE_SHADE = hex_rgb("#1d3c99")
CUFF = hex_rgb("#ffcf1f")
WOOD = hex_rgb("#26262f")
WOOD_LIGHT = hex_rgb("#5b6178")
WOOD_DARK = hex_rgb("#141419")
SILVER = hex_rgb("#d7dce6")
SILVER_SHADE = hex_rgb("#9097a6")
SILVER_LIGHT = (1.0, 1.0, 1.0)
REED = hex_rgb("#e9c77b")
HIGHWAY = hex_rgb("#1e1a33")
HIGHWAY_LANE = hex_rgb("#2c2650")
ACCENT = hex_rgb("#ff2e88")
STAR = hex_rgb("#ffe03a")
STAR_EDGE = hex_rgb("#e8262b")

# Guitar Hero style colour per finger: same finger, same colour on both hands.
FINGER_COLORS = {
    "LT": hex_rgb("#ff8a00"),
    "L1": hex_rgb("#22c55e"), "R1": hex_rgb("#22c55e"),
    "L2": hex_rgb("#ef2b2d"), "R2": hex_rgb("#ef2b2d"),
    "L3": hex_rgb("#ffd21f"), "R3": hex_rgb("#ffd21f"),
    "L4": hex_rgb("#1e88ff"), "R4": hex_rgb("#1e88ff"),
}

# --- clarinet ----------------------------------------------------------------

BODY_Y = 612          # centre line of the instrument
BODY_R = 30           # half thickness of the main tube
BODY_TOP = BODY_Y - BODY_R
BODY_BOTTOM = BODY_Y + BODY_R

MOUTHPIECE = (70, 255)
BARREL = (255, 355)
UPPER_JOINT = (355, 965)
LOWER_JOINT = (965, 1570)
BELL = (1570, 1850)

# Key/hole positions: (x, y, kind) where kind controls how it is drawn.
KEY_POS = {
    "REG": (452, BODY_Y, "back_key"),
    "T": (520, BODY_Y, "back_hole"),
    "A": (598, BODY_TOP - 6, "top_lever"),
    "GS": (642, BODY_TOP - 4, "top_lever"),
    "L1": (700, BODY_Y, "hole"),
    "L2": (790, BODY_Y, "hole"),
    "L3": (880, BODY_Y, "hole"),
    "LE": (998, BODY_BOTTOM + 22, "spatula"),
    "LFS": (1040, BODY_BOTTOM + 32, "spatula"),
    "LCS": (1082, BODY_BOTTOM + 22, "spatula"),
    "S1": (1052, BODY_TOP - 4, "side"),
    "S2": (1080, BODY_TOP - 4, "side"),
    "S3": (1108, BODY_TOP - 4, "side"),
    "S4": (1136, BODY_TOP - 4, "side"),
    "R1": (1182, BODY_Y, "hole"),
    "R2": (1272, BODY_Y, "hole"),
    "R3": (1362, BODY_Y, "hole"),
    "RE": (1440, BODY_BOTTOM + 22, "spatula"),
    "RF": (1482, BODY_BOTTOM + 32, "spatula"),
    "RGS": (1524, BODY_BOTTOM + 22, "spatula"),
}

SHORT_LABELS = {
    "REG": "R", "T": "T", "A": "A", "GS": "G#", "LE": "E", "LFS": "F#", "LCS": "C#",
    "S1": "1", "S2": "2", "S3": "3", "S4": "Eb", "RE": "E", "RF": "F", "RGS": "Ab",
}

# --- highway -------------------------------------------------------------

LANE_X = {"LT": 486, "L1": 700, "L2": 790, "L3": 880, "L4": 1040,
          "R1": 1182, "R2": 1272, "R3": 1362, "R4": 1482}
LANE_W = 66
HIGHWAY_TOP = 214
STRIKE_Y = 536
HIGHWAY_CX = (LANE_X["LT"] + LANE_X["R4"]) / 2
HIGHWAY_FAR_SCALE = 0.56   # lane spread at the far (top) end
HIGHWAY_PAD = 70           # extra width beyond the outer lanes

# --- staff strip ---------------------------------------------------------

STAFF_PANEL = (20, 14, 1880, 186)   # x, y, w, h
STAFF_BOTTOM_LINE = 134              # y of the bottom staff line (E4)
STAFF_SPACE = 14                     # distance between staff lines
STAFF_LEFT = 250                     # notes are clipped left of this
STAFF_PLAYHEAD = 430
STAFF_PX_PER_SEC = 230

# --- hands ---------------------------------------------------------------

# Knuckle (base) of each finger, on the back of the hand.
KNUCKLES = {
    "LT": (668, 900),
    "L1": (684, 806), "L2": (772, 796), "L3": (858, 806), "L4": (934, 830),
    "R1": (1166, 806), "R2": (1256, 796), "R3": (1342, 806), "R4": (1418, 830),
}
FINGER_W = {"LT": 38, "L1": 32, "L2": 34, "L3": 31, "L4": 26,
            "R1": 32, "R2": 34, "R3": 31, "R4": 26}

# Where a fingertip rests when it is not pressing anything.
HOVER = {
    "LT": (590, BODY_BOTTOM + 96),
    "L1": (694, BODY_BOTTOM + 50), "L2": (784, BODY_BOTTOM + 54),
    "L3": (872, BODY_BOTTOM + 50), "L4": (990, BODY_BOTTOM + 78),
    "R1": (1176, BODY_BOTTOM + 50), "R2": (1266, BODY_BOTTOM + 54),
    "R3": (1354, BODY_BOTTOM + 50), "R4": (1448, BODY_BOTTOM + 78),
}

PALMS = {
    "L": {"wrist": (790, 1040), "width": 270},
    "R": {"wrist": (1272, 1040), "width": 270},
}
RH_THUMB = {"base": (1128, 880), "tip": (1226, BODY_Y + 6)}

# --- panels ----------------------------------------------------------------

INFO_PANEL = (28, 700, 400, 352)
NEXT_PANEL = (1560, 700, 332, 352)
