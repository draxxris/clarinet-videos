"""MusicXML loading for a single monophonic clarinet part.

Pitches in a Bb clarinet part are *written* pitches. Fingerings are looked up
from the written pitch, and audio is rendered from the *concert* pitch
(written + transposition, normally -2 semitones for Bb clarinet).
"""

from __future__ import annotations

import bisect
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

STEP_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# Bb clarinet sounds a major second lower than written.
BB_CLARINET_TRANSPOSE = -2


def midi_name(midi: int, prefer_flats: bool = False) -> str:
    names = FLAT_NAMES if prefer_flats else SHARP_NAMES
    return f"{names[midi % 12]}{midi // 12 - 1}"


@dataclass
class Note:
    start_beat: Fraction  # in quarter notes from the start of the piece
    dur_beat: Fraction
    written_midi: int
    concert_midi: int
    step: str  # written spelling, used for drawing on the staff
    octave: int
    alter: int
    accidental: str | None  # displayed accidental from the score, if any
    measure: str
    note_type: str | None = None  # "quarter", "eighth", ...
    dots: int = 0
    start: float = 0.0  # seconds
    end: float = 0.0

    @property
    def name(self) -> str:
        acc = {1: "#", -1: "b", 2: "##", -2: "bb"}.get(self.alter, "")
        return f"{self.step}{acc}{self.octave}"

    @property
    def concert_name(self) -> str:
        return midi_name(self.concert_midi, prefer_flats=self.alter <= 0)

    @property
    def staff_step(self) -> int:
        """Diatonic position: 0 = C4, 1 = D4, ... used for staff placement."""
        return (self.octave - 4) * 7 + "CDEFGAB".index(self.step)


@dataclass
class Rest:
    start_beat: Fraction
    dur_beat: Fraction
    note_type: str | None = None
    start: float = 0.0
    end: float = 0.0


@dataclass
class Measure:
    number: str
    start_beat: Fraction
    start: float = 0.0


@dataclass
class TempoMap:
    """Piecewise-constant tempo, in quarter notes per minute."""

    points: list[tuple[Fraction, float]] = field(default_factory=list)

    def add(self, beat: Fraction, bpm: float) -> None:
        if self.points and self.points[-1][0] == beat:
            self.points[-1] = (beat, bpm)
        elif not self.points or self.points[-1][1] != bpm:
            self.points.append((beat, bpm))

    def seconds(self, beat: Fraction) -> float:
        pts = self.points or [(Fraction(0), 120.0)]
        t = 0.0
        prev_beat, prev_bpm = Fraction(0), pts[0][1]
        for b, bpm in pts:
            if b >= beat:
                break
            t += float(b - prev_beat) * 60.0 / prev_bpm
            prev_beat, prev_bpm = b, bpm
        return t + float(beat - prev_beat) * 60.0 / prev_bpm

    def bpm_at(self, beat: Fraction) -> float:
        pts = self.points or [(Fraction(0), 120.0)]
        idx = bisect.bisect_right([p[0] for p in pts], beat) - 1
        return pts[max(idx, 0)][1]


@dataclass
class Score:
    title: str
    notes: list[Note]
    rests: list[Rest]
    measures: list[Measure]
    tempo: TempoMap
    key_fifths: int
    time_sig: tuple[int, int]
    transpose: int
    total_beats: Fraction

    @property
    def duration(self) -> float:
        return self.tempo.seconds(self.total_beats)

    def beat_to_seconds(self, beat: Fraction) -> float:
        return self.tempo.seconds(beat)


def _read_xml_root(path: Path) -> ET.Element:
    if path.suffix.lower() == ".mxl":
        with zipfile.ZipFile(path) as zf:
            rootfile = None
            if "META-INF/container.xml" in zf.namelist():
                container = ET.fromstring(zf.read("META-INF/container.xml"))
                for el in container.iter():
                    if el.tag.endswith("rootfile") and el.get("full-path"):
                        rootfile = el.get("full-path")
                        break
            if rootfile is None:
                rootfile = next(
                    n for n in zf.namelist()
                    if n.endswith((".xml", ".musicxml")) and not n.startswith("META-INF")
                )
            return ET.fromstring(zf.read(rootfile))
    return ET.parse(path).getroot()


def _strip_namespaces(root: ET.Element) -> None:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def _text(el: ET.Element | None, path: str, default=None):
    if el is None:
        return default
    found = el.find(path)
    return found.text.strip() if found is not None and found.text else default


BEAT_UNIT_QUARTERS = {
    "whole": 4.0, "half": 2.0, "quarter": 1.0, "eighth": 0.5, "16th": 0.25,
}


def load_score(
    path: str | Path,
    part_index: int = 0,
    transpose: int | None = None,
    concert_input: bool = False,
    default_bpm: float = 100.0,
    tempo_override: float | None = None,
) -> Score:
    """Parse a MusicXML (.musicxml/.xml/.mxl) file.

    transpose: semitones from written to concert pitch. Defaults to the
        part's <transpose> element, else -2 (Bb clarinet).
    concert_input: the file is notated at concert pitch (e.g. a "concert
        pitch" export), so written pitch = concert pitch - transpose.
    """
    path = Path(path)
    root = _read_xml_root(path)
    _strip_namespaces(root)
    if root.tag == "score-timewise":
        raise ValueError("score-timewise MusicXML is not supported; export as partwise")

    title = (
        _text(root, "work/work-title")
        or _text(root, "movement-title")
        or path.stem.replace("_", " ").title()
    )
    parts = root.findall("part")
    if not parts:
        raise ValueError("no <part> found in MusicXML")
    part = parts[min(part_index, len(parts) - 1)]

    divisions = 1
    key_fifths = 0
    time_sig = (4, 4)
    file_transpose: int | None = None
    tempo = TempoMap()
    notes: list[Note] = []
    rests: list[Rest] = []
    measures: list[Measure] = []
    target_voice: str | None = None
    first_key = first_time = None

    pos = Fraction(0)
    for m_el in part.findall("measure"):
        m_start = pos
        m_extent = Fraction(0)
        measures.append(Measure(m_el.get("number", str(len(measures) + 1)), m_start))
        last_note_start: Fraction | None = None

        for el in m_el:
            tag = el.tag
            if tag == "attributes":
                divisions = int(_text(el, "divisions", divisions))
                fifths = _text(el, "key/fifths")
                if fifths is not None:
                    key_fifths = int(fifths)
                    first_key = key_fifths if first_key is None else first_key
                beats, beat_type = _text(el, "time/beats"), _text(el, "time/beat-type")
                if beats and beat_type:
                    time_sig = (int(beats.split("+")[0]), int(beat_type))
                    first_time = time_sig if first_time is None else first_time
                if el.find("transpose") is not None and file_transpose is None:
                    chrom = int(_text(el, "transpose/chromatic", 0))
                    octs = int(_text(el, "transpose/octave-change", 0))
                    file_transpose = chrom + 12 * octs
            elif tag in ("direction", "sound"):
                snd = el if tag == "sound" else el.find("sound")
                bpm = None
                if snd is not None and snd.get("tempo"):
                    bpm = float(snd.get("tempo"))
                elif tag == "direction":
                    per_min = _text(el, "direction-type/metronome/per-minute")
                    unit = _text(el, "direction-type/metronome/beat-unit", "quarter")
                    if per_min:
                        try:
                            q = BEAT_UNIT_QUARTERS.get(unit, 1.0)
                            if el.find("direction-type/metronome/beat-unit-dot") is not None:
                                q *= 1.5
                            bpm = float(per_min) * q
                        except ValueError:
                            bpm = None
                if bpm:
                    tempo.add(pos, bpm)
            elif tag == "backup":
                pos -= Fraction(int(_text(el, "duration", 0)), divisions)
            elif tag == "forward":
                pos += Fraction(int(_text(el, "duration", 0)), divisions)
                m_extent = max(m_extent, pos - m_start)
            elif tag == "note":
                if el.find("grace") is not None or el.find("cue") is not None:
                    continue
                dur = Fraction(int(_text(el, "duration", 0)), divisions)
                is_chord = el.find("chord") is not None
                start = last_note_start if (is_chord and last_note_start is not None) else pos
                if not is_chord:
                    last_note_start = pos
                    pos += dur
                    m_extent = max(m_extent, pos - m_start)

                voice = _text(el, "voice", "1")
                staff = _text(el, "staff", "1")
                if staff != "1":
                    continue
                if target_voice is None:
                    target_voice = voice
                if voice != target_voice:
                    continue

                note_type = _text(el, "type")
                dots = len(el.findall("dot"))
                if el.find("rest") is not None:
                    if not is_chord:
                        rests.append(Rest(start, dur, note_type))
                    continue
                pitch = el.find("pitch")
                if pitch is None:  # unpitched
                    continue
                step = _text(pitch, "step")
                octave = int(_text(pitch, "octave"))
                alter_txt = _text(pitch, "alter", "0")
                alter = int(round(float(alter_txt)))
                midi = (octave + 1) * 12 + STEP_SEMITONES[step] + alter
                accidental = _text(el, "accidental")
                ties = [t.get("type") for t in el.findall("tie")]

                if is_chord:
                    # Clarinet is monophonic: keep the top note of a chord.
                    if notes and notes[-1].start_beat == start and midi > notes[-1].written_midi:
                        prev = notes[-1]
                        prev.written_midi, prev.step, prev.octave, prev.alter = midi, step, octave, alter
                        prev.accidental = accidental
                    continue

                if "stop" in ties and notes:
                    prev = notes[-1]
                    if prev.written_midi == midi and prev.start_beat + prev.dur_beat == start:
                        prev.dur_beat += dur
                        continue
                notes.append(Note(start, dur, midi, midi, step, octave, alter, accidental,
                                  measures[-1].number, note_type, dots))
        pos = m_start + m_extent

    if tempo_override:
        tempo = TempoMap([(Fraction(0), tempo_override)])
    elif not tempo.points or tempo.points[0][0] > 0:
        tempo.points.insert(0, (Fraction(0), tempo.points[0][1] if tempo.points else default_bpm))

    if transpose is None:
        transpose = file_transpose if file_transpose is not None else BB_CLARINET_TRANSPOSE
    for n in notes:
        if concert_input:
            # File is in concert pitch: shift notation up to the written pitch.
            n.concert_midi = n.written_midi
            n.written_midi = n.written_midi - transpose
            _respell(n)
        else:
            n.concert_midi = n.written_midi + transpose
        n.start = tempo.seconds(n.start_beat)
        n.end = tempo.seconds(n.start_beat + n.dur_beat)
    for r in rests:
        r.start = tempo.seconds(r.start_beat)
        r.end = tempo.seconds(r.start_beat + r.dur_beat)
    for m in measures:
        m.start = tempo.seconds(m.start_beat)

    if concert_input and first_key is not None:
        first_key = _transpose_fifths(first_key, -transpose)

    return Score(
        title=title,
        notes=notes,
        rests=rests,
        measures=measures,
        tempo=tempo,
        key_fifths=first_key if first_key is not None else key_fifths,
        time_sig=first_time or time_sig,
        transpose=transpose,
        total_beats=pos,
    )


def _transpose_fifths(fifths: int, semitones: int) -> int:
    # Moving up a major second adds two sharps to the key signature.
    out = fifths + (semitones % 12) * 7
    out = (out + 6) % 12 - 6
    return out


def _respell(n: Note) -> None:
    """Spell a MIDI number with sharps (used only after transposition)."""
    pc = n.written_midi % 12
    name = SHARP_NAMES[pc]
    n.step = name[0]
    n.alter = 1 if len(name) > 1 else 0
    n.octave = n.written_midi // 12 - 1
    n.accidental = "sharp" if n.alter else None
