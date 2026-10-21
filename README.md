# clarinet-videos

Turn **Bb clarinet sheet music (MusicXML)** into a play-along video: a comic-book
style clarinet with hands that finger each note, a Rock Band style note highway
that shows what's coming, a scrolling staff, and audio, all exported to MP4.

```
python -m clarinet_viz examples/ode_to_joy.musicxml -o ode_to_joy.mp4
```

## What's on screen

- **Clarinet** (left): a large upright view of the keywork, cropped to the
  upper and lower joints so the keys are easy to see. The register key, thumb
  hole and thumb rest are on the back, so they're drawn dashed. Keys for the
  *next* note pulse in their finger colour as it approaches, and keys in use
  glow while they're held.
- **Hands**: flat, thinly inked hands seen from above, as the player sees
  them: the left hand on the upper joint comes in from the left, the right
  hand on the lower joint from the right. They fade out at the wrist and cast
  soft shadows on the instrument. Each hand is a rigid 2D rig that shifts and
  rotates as one piece so the fingers can reach their keys; fingers are three
  jointed segments of fixed length that curl (foreshorten) off holes they
  aren't covering. Side keys are pressed by rolling the index finger. The
  left thumb reaches under the hand to the back of the instrument and shows
  through faintly where the tube hides it, moving between the thumb hole and
  register key; the right thumb (on the thumb rest) isn't drawn.
- **Note highway** (right, drawn over the right hand): one horizontal lane per finger, lined up with the
  keys it plays and colour coded the same on both hands (thumb orange, index
  green, middle red, ring yellow, pinky blue). Notes scroll in from the right
  to the strike line beside the clarinet; a gem's length is how long to hold
  it. Lever gems are labelled (`A`, `G#`, `T+Reg`, `E`, `F`, `Ab`, `Eb` ...).
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
- `clarinet_viz/scene.py` draws each frame with cairo, `rig.py` poses each
  hand (a small least-squares fit so pressing fingers can reach), `hands.py`
  draws them, `layout.py` holds all positions and colours, and
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
