"""Audio rendering: write a MIDI file of the concert pitches and render it
with FluidSynth and a General MIDI soundfont, or fall back to a simple
built-in synth when FluidSynth isn't available."""

from __future__ import annotations

import shutil
import struct
import subprocess
import wave
from pathlib import Path

import numpy as np

from .score import Score

GM_CLARINET = 71  # General MIDI program 72 "Clarinet", zero-based
SAMPLE_RATE = 44100
TICKS_PER_QUARTER = 480

SOUNDFONT_SEARCH = [
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/default-GM.sf2",
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/share/soundfonts/default.sf2",
    "/opt/homebrew/share/soundfonts/default.sf2",
    "/usr/local/share/soundfonts/default.sf2",
]


def find_soundfont(explicit: str | None = None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"soundfont not found: {p}")
        return p
    for cand in SOUNDFONT_SEARCH:
        if Path(cand).exists():
            return Path(cand)
    return None


def _varlen(value: int) -> bytes:
    buf = [value & 0x7F]
    value >>= 7
    while value:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(buf))


def write_midi(score: Score, path: str | Path, program: int = GM_CLARINET,
               lead_in: float = 0.0) -> None:
    """Write a type-0 MIDI file at concert pitch, with the score's tempo map.

    lead_in: seconds of silence before the first beat (matches the video).
    """
    events: list[tuple[int, int, bytes]] = []  # (tick, order, data)
    lead_ticks = 0
    first_bpm = score.tempo.points[0][1]
    if lead_in > 0:
        lead_ticks = round(lead_in * first_bpm / 60.0 * TICKS_PER_QUARTER)

    def tick(beat) -> int:
        return lead_ticks + round(float(beat) * TICKS_PER_QUARTER)

    events.append((0, 0, b"\xff\x51\x03" + struct.pack(">I", round(60_000_000 / first_bpm))[1:]))
    for beat, bpm in score.tempo.points:
        if beat > 0:
            events.append((tick(beat), 0, b"\xff\x51\x03" + struct.pack(">I", round(60_000_000 / bpm))[1:]))
    events.append((0, 1, bytes([0xC0, program & 0x7F])))
    events.append((0, 1, bytes([0xB0, 7, 110])))  # channel volume
    for n in score.notes:
        start, end = tick(n.start_beat), tick(n.start_beat + n.dur_beat)
        # Release a hair early so repeated notes re-articulate.
        end = max(start + 1, end - 8)
        events.append((start, 3, bytes([0x90, n.concert_midi, 96])))
        events.append((end, 2, bytes([0x80, n.concert_midi, 0])))
    events.sort(key=lambda e: (e[0], e[1]))

    track = bytearray()
    last = 0
    for t, _, data in events:
        track += _varlen(t - last) + data
        last = t
    track += _varlen(TICKS_PER_QUARTER) + b"\xff\x2f\x00"
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TICKS_PER_QUARTER)
    Path(path).write_bytes(header + b"MTrk" + struct.pack(">I", len(track)) + bytes(track))


def render_fluidsynth(midi_path: Path, wav_path: Path, soundfont: Path,
                      gain: float = 0.8) -> None:
    exe = shutil.which("fluidsynth")
    if not exe:
        raise RuntimeError("fluidsynth not found on PATH")
    subprocess.run(
        [exe, "-ni", "-q", "-g", str(gain), "-r", str(SAMPLE_RATE),
         "-F", str(wav_path), "-T", "wav", str(soundfont), str(midi_path)],
        check=True, stdout=subprocess.DEVNULL,
    )


def render_builtin(score: Score, wav_path: Path, lead_in: float = 0.0,
                   tail: float = 1.0) -> None:
    """Rough clarinet-like tone: odd harmonics, soft attack, light vibrato."""
    total = lead_in + score.duration + tail
    out = np.zeros(int(total * SAMPLE_RATE) + 1, dtype=np.float64)
    harmonics = [(1, 1.0), (3, 0.45), (5, 0.25), (7, 0.12), (9, 0.06), (2, 0.08), (4, 0.04)]
    for n in score.notes:
        f0 = 440.0 * 2 ** ((n.concert_midi - 69) / 12)
        dur = max(n.end - n.start - 0.01, 0.03)
        cnt = int(dur * SAMPLE_RATE)
        t = np.arange(cnt) / SAMPLE_RATE
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t / 0.4, 0, 1)
        phase = 2 * np.pi * f0 * np.cumsum(vib) / SAMPLE_RATE
        sig = sum(a * np.sin(h * phase) for h, a in harmonics if h * f0 < SAMPLE_RATE / 2)
        env = np.minimum(1.0, t / 0.03) * np.minimum(1.0, (dur - t) / 0.05)
        start = int((lead_in + n.start) * SAMPLE_RATE)
        out[start:start + cnt] += sig * env * 0.25
    peak = np.max(np.abs(out)) or 1.0
    pcm = (out / peak * 0.8 * 32767).astype("<i2")
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())


def render_audio(score: Score, workdir: Path, lead_in: float, soundfont: str | None = None,
                 engine: str = "auto", program: int = GM_CLARINET) -> tuple[Path, str]:
    """Render the score's audio to a WAV. Returns (path, engine used)."""
    workdir.mkdir(parents=True, exist_ok=True)
    wav = workdir / "audio.wav"
    midi = workdir / "score.mid"
    write_midi(score, midi, program=program, lead_in=lead_in)
    if engine in ("auto", "fluidsynth"):
        sf = find_soundfont(soundfont)
        if sf and shutil.which("fluidsynth"):
            render_fluidsynth(midi, wav, sf)
            return wav, f"fluidsynth ({sf.name})"
        if engine == "fluidsynth":
            raise RuntimeError("fluidsynth or a soundfont is missing; install them or use --audio builtin")
    render_builtin(score, wav, lead_in=lead_in)
    return wav, "builtin synth"
