from clarinet_viz.fingerings import FINGERINGS, KEYS, LOWEST, HIGHEST, fingering_for


def test_full_chromatic_range_covered():
    assert LOWEST == 52 and HIGHEST >= 89
    for midi in range(LOWEST, HIGHEST + 1):
        assert fingering_for(midi) is not None, midi


def test_keys_are_known():
    for midi, fing in FINGERINGS.items():
        assert fing <= set(KEYS), midi


def test_clarion_is_chalumeau_plus_register_key():
    for midi in range(71, 85):
        assert FINGERINGS[midi] == FINGERINGS[midi - 19] | {"REG"}


def test_basic_fingerings():
    assert fingering_for(67) == frozenset()  # open G
    assert fingering_for(60) == {"T", "L1", "L2", "L3"}  # C4
    assert fingering_for(70) == {"A", "REG"}  # Bb4
    assert fingering_for(40) is None
