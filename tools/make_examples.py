"""Generate the example MusicXML files in examples/ (written pitch, Bb clarinet)."""

from pathlib import Path

DIV = 2  # divisions per quarter
TYPES = {1: "eighth", 2: "quarter", 3: ("quarter", 1), 4: "half", 6: ("half", 1), 8: "whole"}
SHARPS = {0: ("C", 0), 1: ("C", 1), 2: ("D", 0), 3: ("E", -1), 4: ("E", 0), 5: ("F", 0),
          6: ("F", 1), 7: ("G", 0), 8: ("G", 1), 9: ("A", 0), 10: ("B", -1), 11: ("B", 0)}


def note_xml(midi, dur):
    t = TYPES[dur]
    typ, dots = (t, 0) if isinstance(t, str) else t
    step, alter = SHARPS[midi % 12]
    octave = midi // 12 - 1
    acc = {1: "<accidental>sharp</accidental>", -1: "<accidental>flat</accidental>"}.get(alter, "")
    alt = f"<alter>{alter}</alter>" if alter else ""
    return (f"<note><pitch><step>{step}</step>{alt}<octave>{octave}</octave></pitch>"
            f"<duration>{dur}</duration><voice>1</voice><type>{typ}</type>{'<dot/>' * dots}{acc}</note>")


def score_xml(title, bpm, measures):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
           '"http://www.musicxml.org/dtds/partwise.dtd">',
           '<score-partwise version="4.0">',
           f'<work><work-title>{title}</work-title></work>',
           '<part-list><score-part id="P1"><part-name>Clarinet in Bb</part-name></score-part></part-list>',
           '<part id="P1">']
    for i, notes in enumerate(measures, 1):
        out.append(f'<measure number="{i}">')
        if i == 1:
            out.append(f'<attributes><divisions>{DIV}</divisions><key><fifths>0</fifths></key>'
                       '<time><beats>4</beats><beat-type>4</beat-type></time>'
                       '<clef><sign>G</sign><line>2</line></clef>'
                       '<transpose><diatonic>-1</diatonic><chromatic>-2</chromatic></transpose></attributes>')
            out.append(f'<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit>'
                       f'<per-minute>{bpm}</per-minute></metronome></direction-type><sound tempo="{bpm}"/></direction>')
        out += [note_xml(m, d) for m, d in notes]
        out.append('</measure>')
    out += ['</part>', '</score-partwise>']
    return "\n".join(out) + "\n"


E, F, G, D, C = 64, 65, 67, 62, 60
q, h, dq, e, w = 2, 4, 3, 1, 8
ode = [
    [(E, q), (E, q), (F, q), (G, q)], [(G, q), (F, q), (E, q), (D, q)],
    [(C, q), (C, q), (D, q), (E, q)], [(E, dq), (D, e), (D, h)],
    [(E, q), (E, q), (F, q), (G, q)], [(G, q), (F, q), (E, q), (D, q)],
    [(C, q), (C, q), (D, q), (E, q)], [(D, dq), (C, e), (C, h)],
]
ode_up = [[(m + 12, d) for m, d in bar] for bar in ode[:7]] + [[(D + 12, dq), (C + 12, e), (C + 12, h)]]

here = Path(__file__).resolve().parent.parent / "examples"
(here / "ode_to_joy.musicxml").write_text(score_xml("Ode to Joy", 96, ode + ode_up))

scale = list(range(52, 90))
bars = [[(m, e) for m in scale[i:i + 8]] for i in range(0, len(scale), 8)]
bars[-1] += [(scale[-1], e)] * (8 - len(bars[-1]))
(here / "chromatic_scale.musicxml").write_text(score_xml("Chromatic Scale E3 to F6", 80, bars))
print("wrote", here)
