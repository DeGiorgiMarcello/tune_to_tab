from tune_to_tab.tab import (
    BASS,
    GUITAR,
    Note,
    assign_positions,
    candidate_fingerings,
    fold_into_range,
    group_chords,
    render_tab,
)


def test_open_low_e_on_guitar_is_string_0_fret_0():
    events = assign_positions([Note(0.0, 0.5, 40)], GUITAR)
    assert events[0].positions == ((0, 0),)


def test_out_of_range_notes_are_folded_by_octave():
    assert fold_into_range(20, BASS) == 32
    assert fold_into_range(100, GUITAR) == 76


def test_simultaneous_notes_are_grouped():
    groups = group_chords([Note(0.0, 1, 40), Note(0.01, 1, 47), Note(0.5, 1, 52)])
    assert groups == [(0.0, [40, 47]), (0.5, [52])]


def test_fingerings_use_distinct_strings():
    for f in candidate_fingerings([40, 45, 50], GUITAR):
        strings = [s for s, _ in f]
        assert len(set(strings)) == len(strings)


def test_e_major_chord_is_playable_in_open_position():
    # E2 B2 E3 G#3 B3 E4
    notes = [Note(0.0, 1, p) for p in (40, 47, 52, 56, 59, 64)]
    (event,) = assign_positions(notes, GUITAR)
    assert sorted(event.positions) == [(0, 0), (1, 2), (2, 2), (3, 1), (4, 0), (5, 0)]


def test_bass_is_monophonic_and_keeps_lowest_note():
    notes = [Note(0.0, 1, 33), Note(0.0, 1, 45)]
    (event,) = assign_positions(notes, BASS)
    assert event.positions == ((1, 0),)


def test_melody_stays_in_one_hand_position():
    # A3 B3 C#4 D4: should be played without big position shifts
    notes = [Note(i * 0.25, i * 0.25 + 0.2, p) for i, p in enumerate((57, 59, 61, 62))]
    events = assign_positions(notes, GUITAR)
    frets = [f for ev in events for _, f in ev.positions if f > 0]
    assert max(frets) - min(frets) <= 4


def test_render_contains_one_row_per_string_and_frets():
    events = assign_positions([Note(0.0, 0.2, 40), Note(0.5, 0.7, 52)], GUITAR)
    text = render_tab(events, GUITAR, bpm=120)
    tab_rows = [r for r in text.splitlines() if r[:2] in {"e|", "B|", "G|", "D|", "A|", "E|"}]
    assert len(tab_rows) == 6
    assert tab_rows[-1].startswith("E|0")  # low E at the bottom
    assert "2" in tab_rows[3]  # E3 = D string fret 2
