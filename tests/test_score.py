from fractions import Fraction
from pathlib import Path

from clarinet_viz.score import load_score

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

MINI = """<?xml version="1.0"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Cl</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
      <direction><sound tempo="60"/></direction>
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type><tie type="start"/></note>
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type><tie type="stop"/></note>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type></note>
      <note><chord/><pitch><step>G</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type></note>
      <note><rest/><duration>4</duration><voice>1</voice><type>quarter</type></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>A</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type></note>
    </measure>
    <measure number="2">
      <note><pitch><step>F</step><alter>1</alter><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type></note>
    </measure>
  </part>
</score-partwise>
"""


def test_example_parses_with_bb_transposition():
    s = load_score(EXAMPLES / "ode_to_joy.musicxml")
    assert s.transpose == -2
    assert len(s.notes) == 60
    first = s.notes[0]
    assert first.name == "E4" and first.concert_name == "D4"
    assert abs(first.end - 60 / 96) < 1e-9


def test_ties_chords_rests_and_voices(tmp_path):
    p = tmp_path / "mini.musicxml"
    p.write_text(MINI)
    s = load_score(p)
    names = [n.name for n in s.notes]
    # Tied C5s merge, the chord keeps its top note, voice 2 is ignored.
    assert names == ["C5", "G4", "F#4"]
    assert s.notes[0].dur_beat == 2
    assert s.notes[2].start_beat == 4
    assert len(s.rests) == 1 and s.rests[0].start_beat == 3
    assert s.notes[2].start == 4.0  # 60 bpm
    assert s.total_beats == Fraction(8)


def test_concert_input_shifts_to_written(tmp_path):
    p = tmp_path / "mini.musicxml"
    p.write_text(MINI)
    s = load_score(p, concert_input=True)
    # Concert C5 is written D5 for Bb clarinet.
    assert s.notes[0].concert_midi == 72
    assert s.notes[0].written_midi == 74
    assert s.notes[0].name == "D5"


def test_tempo_override():
    s = load_score(EXAMPLES / "ode_to_joy.musicxml", tempo_override=120)
    assert abs(s.notes[1].start - 0.5) < 1e-9
