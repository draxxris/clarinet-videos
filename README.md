# clarinet-videos

Turn **Bb clarinet sheet music (MusicXML)** into a play-along video: a comic-book
style clarinet whose keys light up for each note, a Rock Band style note highway
that shows what's coming, a scrolling staff, and audio, all exported to MP4.

```
python -m clarinet_viz examples/ode_to_joy.musicxml -o ode_to_joy.mp4
```

## What's on screen

- **Fingering chart** (left): the clarinet as a standard teacher's fingering
  chart, copied from a reference: a teardrop register key, the thumb hole,
  three holes per hand with a line between the hands, the right-hand side
  keys, and four staggered right-pinky keys. Open keys are outlines; keys in
  use fill with their finger's colour, and the next note's keys get a pulsing
  ring. The reference has no A, G# or left-pinky keys, but some notes need
  them, so those are added in the same plain style (the left pinky's three
  keys sit above the divider; A and G# beside the first hole).
- **Note highway** (right): one horizontal lane per finger, lined up with the
  keys it plays and colour coded the same for both hands (thumb orange, index
  green, middle red, ring yellow, pinky blue). Notes scroll in from the right
  to the strike line beside the clarinet; a gem's length is how long to hold
  it. Fingers that work keys beyond a plain hole (thumb, left index, both
  pinkies, right index on the side key) carry a mini copy of that part of the
  chart on the front of each gem with the key to press filled in, plus its
  name when there's room (`T+Reg`, `A`, `G#`, `C#`, `Ab`, `Eb` ...).
- **Staff** (top): the written part on the same timeline as the highway, so
  each note sits directly above its gems, with note-name tags underneath.
- **Now playing** (top left): the written note, the concert pitch it sounds,
  the register, what's next, the bar and the tempo.

## Install

Needs Python 3.10+, [ffmpeg](https://ffmpeg.org/), cairo, and (recommended)
[FluidSynth](https://www.fluidsynth.org/) with a General MIDI soundfont.

```
# Debian/Ubuntu
sudo apt install ffmpeg fluidsynth fluid-soundfont-gm libcairo2-dev
# macOS
brew install ffmpeg fluid-synth cairo pkg-config

pip install -e .            # installs pycairo and numpy
```

On macOS Homebrew's fluid-synth doesn't ship a soundfont; download one (e.g.
FluidR3_GM.sf2 or MuseScore_General.sf2) and pass `--soundfont path/to.sf2`.

## Usage

```
python -m clarinet_viz SCORE.musicxml [-o out.mp4] [options]
```

| option | |
|---|---|
| `--size 1280x720` | output resolution (default 1920x1080) |
| `--fps 30` | frame rate |
| `--tempo 80` | override the score's tempo (quarter notes per minute) |
| `--lookahead 3` | seconds of upcoming music on the highway (default about 3) |
| `--lead-in 2.5` | seconds before the first note |
| `--soundfont FILE.sf2` | soundfont for FluidSynth |
| `--audio builtin` | use the built-in synth instead of FluidSynth |
| `--wav audio.wav` | also save the audio track |
| `--frame 12.5` | write a PNG still at 12.5 s instead of a video (repeatable) |
| `--start/--end` | render only part of the piece |
| `--concert-input` | the file is notated at concert pitch; transpose it up to written pitch |
| `--transpose N` | semitones from written to concert (default: from the file, else -2) |
| `--part N` | which part to use in a multi-part score |

Accepts `.musicxml`, `.xml` and compressed `.mxl` (export from MuseScore,
Finale, Sibelius, Dorico, etc.).

## How it works

- `clarinet_viz/score.py` parses MusicXML: tempo changes, ties, rests, chords
  (keeps the top note), multiple voices (uses the first), and the part's
  `<transpose>` element. Pitches in a Bb clarinet part are **written** pitches;
  fingerings use the written pitch and audio uses the concert pitch (a major
  second lower).
- `clarinet_viz/fingerings.py` is the Boehm fingering chart, written E3 to F6.
  Clarion notes are the chalumeau fingering a twelfth below plus the register
  key. Edit this table to change a fingering.
- `clarinet_viz/audio.py` writes a MIDI file at concert pitch and renders it
  with FluidSynth using the soundfont's clarinet patch (GM program 72). Without
  FluidSynth it falls back to a simple additive synth.
- `clarinet_viz/scene.py` draws each frame with cairo, `layout.py` holds all
  positions and colours, and
  `render.py` pipes raw frames to ffmpeg with the audio.

## Limitations

- One monophonic line: chords keep their top note; other voices are ignored.
- Repeats and D.C./D.S. jumps are not expanded yet; write them out in your
  notation program, or "unroll repeats" on export.
- Only the standard fingering per note; alternates (e.g. side Bb, chromatic F#)
  aren't chosen from context. Altissimo fingerings vary by instrument.
- Grace notes are skipped.

## Development

```
pip install -e '.[test]'
python -m pytest
python tools/make_examples.py   # regenerate examples/
```
