"""Command line interface: python -m clarinet_viz score.musicxml -o out.mp4"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .fingerings import fingering_for
from .render import export_video, render_frame_png
from .scene import Scene
from .score import load_score


def parse_size(s: str) -> tuple[int, int]:
    w, h = s.lower().split("x")
    return int(w), int(h)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="clarinet_viz",
        description="Render a Bb clarinet MusicXML score as a play-along video "
                    "with fingerings, a note highway and audio.")
    ap.add_argument("score", help="MusicXML file (.musicxml, .xml or .mxl)")
    ap.add_argument("-o", "--output", help="output video (default: <score>.mp4)")
    ap.add_argument("--part", type=int, default=0, help="part index to use (default 0)")
    ap.add_argument("--size", default="1920x1080", help="video size, e.g. 1280x720")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--tempo", type=float, help="override tempo (quarter notes per minute)")
    ap.add_argument("--transpose", type=int,
                    help="semitones from written to concert pitch (default: from file, else -2)")
    ap.add_argument("--concert-input", action="store_true",
                    help="the file is notated at concert pitch; show written clarinet pitch")
    ap.add_argument("--lead-in", type=float, default=2.5, help="seconds before the first note")
    ap.add_argument("--lookahead", type=float, default=2.8,
                    help="seconds of upcoming music shown on the highway")
    ap.add_argument("--soundfont", help="General MIDI .sf2 soundfont for FluidSynth")
    ap.add_argument("--audio", choices=["auto", "fluidsynth", "builtin"], default="auto",
                    help="audio engine (default: FluidSynth if available, else built-in synth)")
    ap.add_argument("--wav", help="also save the rendered audio to this WAV file")
    ap.add_argument("--start", type=float, default=0.0, help="render from this time (s)")
    ap.add_argument("--end", type=float, help="stop rendering at this time (s)")
    ap.add_argument("--frame", type=float, action="append",
                    help="write a PNG still at this time (s) instead of a video; repeatable")
    ap.add_argument("--crf", type=int, default=20, help="x264 quality (lower is better)")
    args = ap.parse_args(argv)

    score = load_score(args.score, part_index=args.part, transpose=args.transpose,
                       concert_input=args.concert_input, tempo_override=args.tempo)
    if not score.notes:
        sys.exit("no notes found in the score")
    missing = sorted({n.name for n in score.notes if fingering_for(n.written_midi) is None})
    if missing:
        print(f"warning: no fingering for {', '.join(missing)} (outside E3-F6)", file=sys.stderr)
    print(f"{score.title}: {len(score.notes)} notes, {score.duration:0.1f}s, "
          f"written->concert {score.transpose:+d} semitones", file=sys.stderr)

    scene = Scene(score, lead_in=args.lead_in, lookahead=args.lookahead)
    width, height = parse_size(args.size)
    stem = Path(args.output or Path(args.score).with_suffix(".mp4"))
    if args.frame:
        for t in args.frame:
            out = stem.with_name(f"{stem.stem}_{t:06.2f}s.png")
            render_frame_png(scene, t, out, width, height)
            print(f"wrote {out}", file=sys.stderr)
        return
    export_video(scene, stem, fps=args.fps, width=width, height=height,
                 soundfont=args.soundfont, audio_engine=args.audio, crf=args.crf,
                 start=args.start, end=args.end, keep_audio=args.wav,
                 log=lambda m: print(m, file=sys.stderr, flush=True))


if __name__ == "__main__":
    main()
