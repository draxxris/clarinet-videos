from pathlib import Path

from clarinet_viz.audio import write_midi
from clarinet_viz.render import make_surface
from clarinet_viz.scene import Scene
from clarinet_viz.score import load_score

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_frames_render_and_fingers_press():
    s = load_score(EXAMPLES / "ode_to_joy.musicxml")
    scene = Scene(s, lead_in=1.0)
    surf, ctx = make_surface(320, 180)
    for t in (0.0, 1.0, 1.3, 20.0, scene.duration - 0.1):
        scene.render(ctx, t)
    # First note E4 = thumb + left index: index finger is down mid-note.
    first = scene.events[0]
    mid = (first.start + first.end) / 2
    _, pressed = scene.finger_tip("L1", mid)
    assert pressed == 1.0
    _, pressed = scene.finger_tip("L2", mid)
    assert pressed == 0.0


def test_midi_written_at_concert_pitch(tmp_path):
    s = load_score(EXAMPLES / "ode_to_joy.musicxml")
    out = tmp_path / "o.mid"
    write_midi(s, out)
    data = out.read_bytes()
    assert data[:4] == b"MThd"
    # First note-on is concert D4 (62).
    i = data.index(bytes([0x90]))
    assert data[i + 1] == 62
