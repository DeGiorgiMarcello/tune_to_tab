import guitarpro as gp
import pytest

from tune_to_tab.gp import split_duration, tab_to_gp
from tune_to_tab.tab import BASS, GUITAR, Note, assign_positions


def _beat_slots(beat, slot_value=16):
    length = slot_value // beat.duration.value
    return length * 3 // 2 if beat.duration.isDotted else length


def test_split_duration_uses_single_value_when_possible():
    assert split_duration(4, 16) == [(4, False)]  # quarter
    assert split_duration(6, 16) == [(4, True)]  # dotted quarter
    assert split_duration(16, 16) == [(1, False)]  # whole


def test_split_duration_covers_odd_lengths():
    parts = split_duration(5, 16)
    total = sum((16 // v) * (1.5 if d else 1) for v, d in parts)
    assert total == 5


def test_gp_roundtrip_keeps_pitches_and_full_measures(tmp_path):
    pitches = [40, 47, 52, 55, 59, 64, 62, 57]
    notes = [Note(i * 0.375, i * 0.375 + 0.3, p) for i, p in enumerate(pitches)]  # dotted eighths at 120 BPM
    events = assign_positions(notes, GUITAR)
    path = tab_to_gp(events, GUITAR, bpm=120, path=tmp_path / "guitar.gp5", title="demo")

    song = gp.parse(str(path))
    track = song.tracks[0]
    assert [s.value for s in sorted(track.strings, key=lambda s: -s.number)] == list(GUITAR.tuning)

    played = [
        n.realValue
        for m in track.measures
        for b in m.voices[0].beats
        for n in b.notes
        if n.type == gp.NoteType.normal
    ]
    assert played == pitches
    for m in track.measures:
        assert sum(_beat_slots(b) for b in m.voices[0].beats) == 16


def test_gp_bass_has_four_strings(tmp_path):
    events = assign_positions([Note(0.0, 0.4, 28), Note(0.5, 0.9, 33)], BASS)
    song = gp.parse(str(tab_to_gp(events, BASS, bpm=120, path=tmp_path / "bass.gp5")))
    assert len(song.tracks[0].strings) == 4


def test_gp_rejects_triplet_grid(tmp_path):
    with pytest.raises(ValueError):
        tab_to_gp([], GUITAR, bpm=120, path=tmp_path / "x.gp5", subdivisions_per_beat=3)
