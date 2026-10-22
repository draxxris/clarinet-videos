from pathlib import Path

from clarinet_viz.audio import write_midi
from clarinet_viz.render import make_surface
from clarinet_viz.scene import Scene
from clarinet_viz.score import load_score

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_frames_render_and_first_fingering():
    s = load_score(EXAMPLES / "ode_to_joy.musicxml")
    scene = Scene(s, lead_in=1.0)
    surf, ctx = make_surface(320, 180)
    for t in (0.0, 1.0, 1.3, 20.0, scene.duration - 0.1):
        scene.render(ctx, t)
    # First note E4 = thumb + left index, and it is the one sounding mid-note.
    first = scene.events[0]
    cur, _ = scene.current((first.start + first.end) / 2)
    assert cur is first
    assert set(first.by_finger) == {"LT", "L1"}


def test_midi_written_at_concert_pitch(tmp_path):
    s = load_score(EXAMPLES / "ode_to_joy.musicxml")
    out = tmp_path / "o.mid"
    write_midi(s, out)
    data = out.read_bytes()
    assert data[:4] == b"MThd"
    # First note-on is concert D4 (62).
    i = data.index(bytes([0x90]))
    assert data[i + 1] == 62
