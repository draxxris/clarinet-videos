"""Boehm-system Bb clarinet fingerings, indexed by *written* MIDI pitch.

Each fingering is the set of holes covered and keys pressed. The chart covers
the standard fingering for each note; alternates are not chosen automatically.

Key ids:
  T      left thumb hole            REG   register key (left thumb)
  A      A key (left index)         GS    G# key (left index)
  L1-L3  left hand finger holes     R1-R3 right hand finger holes
  LE     left pinky E/B             LFS   left pinky F#/C#
  LCS    left pinky C#/G#
  RE     right pinky E/B            RF    right pinky F/C
  RGS    right pinky G#/D# (Ab/Eb)
  S1-S4  right hand side keys (S4 = side Eb/Bb), pressed by the right index
"""

from __future__ import annotations

from dataclasses import dataclass

# Fingers, in lane order (left to right on screen: mouthpiece -> bell).
FINGERS = ["LT", "L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"]

FINGER_NAMES = {
    "LT": "L thumb", "L1": "L index", "L2": "L middle", "L3": "L ring", "L4": "L pinky",
    "R1": "R index", "R2": "R middle", "R3": "R ring", "R4": "R pinky",
}


@dataclass(frozen=True)
class KeyDef:
    id: str
    finger: str
    label: str
    kind: str  # "hole" (finger covers it) or "key" (finger presses a lever)


KEYS = {k.id: k for k in [
    KeyDef("REG", "LT", "Reg", "key"),
    KeyDef("T", "LT", "T", "hole"),
    KeyDef("A", "L1", "A", "key"),
    KeyDef("GS", "L1", "G#", "key"),
    KeyDef("L1", "L1", "1", "hole"),
    KeyDef("L2", "L2", "2", "hole"),
    KeyDef("L3", "L3", "3", "hole"),
    KeyDef("LE", "L4", "E/B", "key"),
    KeyDef("LFS", "L4", "F#/C#", "key"),
    KeyDef("LCS", "L4", "C#/G#", "key"),
    KeyDef("S1", "R1", "S1", "key"),
    KeyDef("S2", "R1", "S2", "key"),
    KeyDef("S3", "R1", "S3", "key"),
    KeyDef("S4", "R1", "Eb/Bb", "key"),
    KeyDef("R1", "R1", "1", "hole"),
    KeyDef("R2", "R2", "2", "hole"),
    KeyDef("R3", "R3", "3", "hole"),
    KeyDef("RE", "R4", "E/B", "key"),
    KeyDef("RF", "R4", "F/C", "key"),
    KeyDef("RGS", "R4", "G#/D#", "key"),
]}

_LH = ("T", "L1", "L2", "L3")
_ALL = _LH + ("R1", "R2", "R3")


def _f(*keys: str) -> frozenset[str]:
    return frozenset(keys)


# Chalumeau register, written E3 (52) .. Bb4 (70).
_CHALUMEAU = {
    52: _f(*_ALL, "LE"),        # E3
    53: _f(*_ALL, "RF"),        # F3
    54: _f(*_ALL, "LFS"),       # F#3
    55: _f(*_ALL),              # G3
    56: _f(*_ALL, "RGS"),       # G#3
    57: _f(*_LH, "R1", "R2"),   # A3
    58: _f(*_LH, "R1"),         # Bb3
    59: _f(*_LH, "R2"),         # B3
    60: _f(*_LH),               # C4
    61: _f(*_LH, "LCS"),        # C#4
    62: _f("T", "L1", "L2"),    # D4
    63: _f("T", "L1", "L2", "S4"),  # Eb4 (side Eb/Bb key)
    64: _f("T", "L1"),          # E4
    65: _f("T"),                # F4
    66: _f("L1"),               # F#4
    67: _f(),                   # G4 (open)
    68: _f("GS"),               # G#4
    69: _f("A"),                # A4
    70: _f("A", "REG"),         # Bb4
}

FINGERINGS: dict[int, frozenset[str]] = dict(_CHALUMEAU)

# Clarion register B4 (71) .. C6 (84): chalumeau fingering a twelfth below
# plus the register key.
for _midi in range(71, 85):
    FINGERINGS[_midi] = _CHALUMEAU[_midi - 19] | {"REG"}

# Altissimo, C#6..F6 (common fingerings; the right pinky Ab/Eb key steadies
# them). Altissimo fingerings vary by instrument, so check these with a teacher.
FINGERINGS.update({
    85: _f("T", "REG", "L2", "L3", "R1", "R2", "R3", "RGS"),  # C#6
    86: _f("T", "REG", "L2", "L3", "R1", "R2", "RGS"),        # D6
    87: _f("T", "REG", "L2", "L3", "R1", "RGS"),              # Eb6
    88: _f("T", "REG", "L2", "L3", "RGS"),                    # E6
    89: _f("T", "REG", "L2", "RGS"),                          # F6
})

LOWEST = min(FINGERINGS)
HIGHEST = max(FINGERINGS)


def fingering_for(written_midi: int) -> frozenset[str] | None:
    """Fingering for a written pitch, or None if outside the chart's range."""
    return FINGERINGS.get(written_midi)


def fingers_used(fingering: frozenset[str]) -> dict[str, list[str]]:
    """Group a fingering's keys by the finger that operates them."""
    out: dict[str, list[str]] = {}
    for k in sorted(fingering):
        out.setdefault(KEYS[k].finger, []).append(k)
    return out
