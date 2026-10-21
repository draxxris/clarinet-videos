"""Scene geometry and colours. Everything is laid out on a 1920x1080 canvas
and scaled to the output size.

The clarinet stands upright on the left, cropped to the keywork (no
mouthpiece or bell). Each finger has a horizontal lane at the height of the
keys it plays; notes scroll in from the right toward a strike line beside
the instrument. The staff along the top shares the highway's timeline, so a
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

SKIN_LIGHT = hex_rgb("#fae4c9")
SKIN = hex_rgb("#f4d6b3")
SKIN_SHADE = hex_rgb("#dcae88")
SKIN_LINE = hex_rgb("#3b2a24")
NAIL = hex_rgb("#f6dcc4")
NAIL_LIGHT = hex_rgb("#fbe9d8")

WOOD_EDGE = hex_rgb("#060608")
WOOD = hex_rgb("#1d1d24")
WOOD_MID = hex_rgb("#34364a")
WOOD_SHINE = hex_rgb("#7c829e")
SILVER_LIGHT = hex_rgb("#ffffff")
SILVER = hex_rgb("#cfd4dd")
SILVER_SHADE = hex_rgb("#8d94a3")
SILVER_DARK = hex_rgb("#5a606e")

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

# --- clarinet ----------------------------------------------------------------

BODY_X = 560          # centre line of the instrument
BODY_R = 58           # half width of the tube
BODY_LEFT = BODY_X - BODY_R
BODY_RIGHT = BODY_X + BODY_R
BODY_TOP = 150        # cropped above the register key
TENON_Y = 562         # joint between upper and lower joints
THUMB_REST_Y = 778

HOLE_R = 22

# Key/hole positions: (x, y, kind) where kind controls how it is drawn.
KEY_POS = {
    "REG": (BODY_X, 216, "back_key"),
    "T": (BODY_X, 262, "back_hole"),
    "A": (BODY_X - 4, 292, "front_lever"),
    "GS": (BODY_RIGHT + 4, 304, "side_lever"),
    "L1": (BODY_X, 336, "hole"),
    "L2": (BODY_X, 420, "hole"),
    "L3": (BODY_X, 504, "hole"),
    "LE": (BODY_LEFT - 16, 594, "spatula"),
    "LFS": (BODY_LEFT - 24, 624, "spatula"),
    "LCS": (BODY_LEFT - 16, 654, "spatula"),
    "S1": (BODY_RIGHT + 2, 610, "side"),
    "S2": (BODY_RIGHT + 2, 634, "side"),
    "S3": (BODY_RIGHT + 2, 658, "side"),
    "S4": (BODY_RIGHT + 2, 684, "side"),
    "R1": (BODY_X, 738, "hole"),
    "R2": (BODY_X, 822, "hole"),
    "R3": (BODY_X, 906, "hole"),
    "RE": (BODY_RIGHT + 16, 980, "spatula"),
    "RF": (BODY_RIGHT + 24, 1010, "spatula"),
    "RGS": (BODY_RIGHT + 16, 1040, "spatula"),
}

SHORT_LABELS = {
    "REG": "Reg", "T": "T", "A": "A", "GS": "G#", "LE": "E", "LFS": "F#", "LCS": "C#",
    "S1": "1", "S2": "2", "S3": "3", "S4": "Eb", "RE": "E", "RF": "F", "RGS": "Ab",
}

# --- highway -------------------------------------------------------------

LANE_Y = {"LT": 240, "L1": 336, "L2": 420, "L3": 504, "L4": 624,
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

# --- hands ---------------------------------------------------------------

# Knuckle (MCP joint) of each finger, in each hand's own frame. Both hands
# are modelled reaching in from the left; the right hand is mirrored across
# the instrument so it comes in from the right, as seen looking down at the
# clarinet while playing.
KNUCKLES = {
    "L1": (372, 350), "L2": (360, 421), "L3": (366, 490), "L4": (378, 556),
    "R1": (372, 752), "R2": (360, 823), "R3": (366, 892), "R4": (378, 958),
}
FINGER_W = {"L1": 52, "L2": 55, "L3": 51, "L4": 44,
            "R1": 52, "R2": 55, "R3": 51, "R4": 44, "LT": 52}
MIRRORED = {"L": False, "R": True}

# The key each finger rests near. Finger lengths come from the rest pose:
# each fingertip reaches its home key at REACH of the finger's full length.
HOME = {"LT": "T", "L1": "L1", "L2": "L2", "L3": "L3", "L4": "LFS",
        "R1": "R1", "R2": "R2", "R3": "R3", "R4": "RF"}
REACH = 0.93
CURL = 0.58  # a lifted finger curls toward the viewer to this share of its length

# Back of each hand (in the hand's frame): knuckles on the right, wrist off
# to the left.
HANDS = {
    "L": {"wrist": (110, 456), "wrist_half": 112, "fingers": ["L1", "L2", "L3", "L4"],
          "thumb_base": (250, 444), "pivot": (240, 456)},
    "R": {"wrist": (110, 860), "wrist_half": 112, "fingers": ["R1", "R2", "R3", "R4"],
          "thumb_base": (250, 850), "pivot": (240, 860)},
}

SHADOW_OFFSET = (16, 20)
