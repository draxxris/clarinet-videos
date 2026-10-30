"""Frame rendering and MP4 export through ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import cairo

from . import layout as L
from .audio import render_audio
from .scene import Scene


def make_surface(width: int, height: int) -> tuple[cairo.ImageSurface, cairo.Context]:
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surf)
    ctx.scale(width / L.W, height / L.H)
    return surf, ctx


def render_frame_png(scene: Scene, t: float, path: str | Path, width: int = 1920,
                     height: int = 1080) -> None:
    surf, ctx = make_surface(width, height)
    scene.render(ctx, t)
    surf.write_to_png(str(path))


def export_video(scene: Scene, out_path: str | Path, fps: int = 30, width: int = 1920,
                 height: int = 1080, soundfont: str | None = None, audio_engine: str = "auto",
                 crf: int = 20, start: float = 0.0, end: float | None = None,
                 keep_audio: str | None = None, log=print) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    end = scene.duration if end is None else min(end, scene.duration)
    with tempfile.TemporaryDirectory(prefix="clarinet_viz_") as tmp:
        wav, engine = render_audio(scene.score, Path(tmp), lead_in=scene.lead_in,
                                   soundfont=soundfont, engine=audio_engine)
        log(f"audio: {engine}")
        if keep_audio:
            shutil.copy(wav, keep_audio)
        cmd = [
            ffmpeg, "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}", "-r", str(fps),
            "-i", "-",
            "-ss", f"{start:.3f}", "-i", str(wav),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-af", "apad", "-shortest",
            "-movflags", "+faststart", str(out_path),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        surf, ctx = make_surface(width, height)
        n_frames = int((end - start) * fps)
        t0 = time.time()
        try:
            for i in range(n_frames):
                t = start + i / fps
                ctx.save()
                scene.render(ctx, t)
                ctx.restore()
                surf.flush()
                proc.stdin.write(surf.get_data())
                if i % (fps * 5) == 0:
                    el = time.time() - t0
                    log(f"frame {i}/{n_frames}  ({el:0.0f}s elapsed)")
        finally:
            proc.stdin.close()
            ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"ffmpeg exited with status {ret}")
    log(f"wrote {out_path} ({n_frames} frames, {time.time() - t0:0.0f}s)")

