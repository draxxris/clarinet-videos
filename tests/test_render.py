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


def test_chart_has_every_key_and_icons_cover_multi_key_fingers():
    from clarinet_viz import layout as L
    from clarinet_viz.fingerings import FINGERINGS, KEYS
    from clarinet_viz.scene import ICON_FINGERS

    assert set(L.KEY_SHAPE) == set(KEYS)
    # Every key some fingering presses has a place on the chart (RE is the
    # chart's spare right-pinky key, kept for completeness).
    assert set().union(*FINGERINGS.values()) <= set(L.KEY_SHAPE)
    assert ICON_FINGERS == {"LT", "L1", "L4", "R1", "R4"}
