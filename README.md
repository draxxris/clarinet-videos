# clarinet-videos

Turn **Bb clarinet sheet music (MusicXML)** into a play-along video: a comic-book
style clarinet with hands that finger each note, a Rock Band style note highway
that shows what's coming, a scrolling staff, and audio, all exported to MP4.

```
python -m clarinet_viz examples/ode_to_joy.musicxml -o ode_to_joy.mp4
```

## What's on screen

- **Scrolling staff** (top): the written part on a treble staff, moving right to
  left in real time past a playhead. The note being played turns pink, and a
  band behind each note shows how long it's held.
- **Note highway** (middle): one lane per finger, colour coded the same on both
  hands (thumb orange, index green, middle red, ring yellow, pinky blue). Gems
  scroll down onto the strike line just above the matching key; the gem's tail
  is how long to hold it. Gems for levers are labelled (`A`, `G#`, `T+R` for
  thumb plus register key, `E`, `F`, `Ab`, `Eb` ...), and each row is tagged
  with the note name.
- **Clarinet and hands**: keys needed for the *next* note pulse in their finger
  colour as it approaches; keys in use light up with a comic "pow" when pressed.
  Fingers move between keys and hover off the holes they aren't covering. The
  left thumb, register key and thumb hole are on the back of the instrument, so
  they're drawn ghosted/dashed.
- **Now playing / coming up** panels: the written note, the concert pitch it
  sounds, the register (chalumeau, throat, clarion, altissimo), a mini fingering
  diagram, and the next few notes with a beat countdown.

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
| `--lookahead 2.8` | seconds of upcoming music on the highway |
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
- `clarinet_viz/scene.py` draws each frame with cairo; `layout.py` holds all
  positions and colours; `render.py` pipes raw frames to ffmpeg with the audio.

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
