"""Export of tab events to a Guitar Pro 5 file (.gp5), readable by Guitar Pro, TuxGuitar and MuseScore."""

from __future__ import annotations

from pathlib import Path

import guitarpro as gp

from .tab import Grid, Instrument, TabEvent, quantize

# General MIDI programs (0-based) used for playback in Guitar Pro.
MIDI_PROGRAMS = {"guitar": 25, "bass": 33}  # acoustic steel guitar, electric bass (finger)
GP_VERSION = (5, 1, 0)


def _is_power_of_two(n: int) -> bool:
    return n > 0 and n & (n - 1) == 0


def split_duration(slots: int, slot_value: int) -> list[tuple[int, bool]]:
    """Split a length in grid slots into Guitar Pro durations.

    `slot_value` is the note value of one slot (16 = sixteenth). Returns a list of
    (duration_value, is_dotted) whose total length equals `slots`.
    """
    # (length in slots, value, dotted), longest first
    sizes = []
    value = 1
    while value <= slot_value:
        length = slot_value // value
        if length % 2 == 0:
            sizes.append((length * 3 // 2, value, True))
        sizes.append((length, value, False))
        value *= 2
    sizes.sort(key=lambda x: -x[0])

    parts = []
    while slots > 0:
        length, value, dotted = next(s for s in sizes if s[0] <= slots)
        parts.append((value, dotted))
        slots -= length
    return parts


def _add_beat(voice: gp.Voice, value: int, dotted: bool, positions: dict[int, int], n_strings: int, tie: bool) -> None:
    beat = gp.Beat(voice, duration=gp.Duration(value=value, isDotted=dotted))
    if positions:
        beat.status = gp.BeatStatus.normal
        for s, fret in sorted(positions.items()):
            beat.notes.append(
                gp.Note(
                    beat,
                    value=fret,
                    string=n_strings - s,  # Guitar Pro numbers strings from the highest (1)
                    type=gp.NoteType.tie if tie else gp.NoteType.normal,
                )
            )
    else:
        beat.status = gp.BeatStatus.rest
    voice.beats.append(beat)


def _fill_measure(voice: gp.Voice, grid: Grid, bar_start: int, slots_per_bar: int, slot_value: int, n_strings: int) -> None:
    onsets = sorted(s for s in grid if bar_start <= s < bar_start + slots_per_bar)
    cursor = bar_start
    for i, onset in enumerate(onsets):
        if onset > cursor:  # rest before the note
            for value, dotted in split_duration(onset - cursor, slot_value):
                _add_beat(voice, value, dotted, {}, n_strings, tie=False)
        # the note rings until the next onset or the end of the bar; extra pieces are tied
        end = onsets[i + 1] if i + 1 < len(onsets) else bar_start + slots_per_bar
        for k, (value, dotted) in enumerate(split_duration(end - onset, slot_value)):
            _add_beat(voice, value, dotted, grid[onset], n_strings, tie=k > 0)
        cursor = end
    if cursor < bar_start + slots_per_bar:
        for value, dotted in split_duration(bar_start + slots_per_bar - cursor, slot_value):
            _add_beat(voice, value, dotted, {}, n_strings, tie=False)


def tab_to_gp(
    events: list[TabEvent],
    inst: Instrument,
    bpm: float,
    path: Path,
    subdivisions_per_beat: int = 4,
    beats_per_bar: int = 4,
    title: str = "",
) -> Path:
    """Write the events as a single-track Guitar Pro 5 file."""
    if not _is_power_of_two(subdivisions_per_beat):
        raise ValueError(f"Guitar Pro export needs a power-of-two subdivision, got {subdivisions_per_beat}")

    grid = quantize(events, bpm, subdivisions_per_beat)
    slots_per_bar = subdivisions_per_beat * beats_per_bar
    slot_value = 4 * subdivisions_per_beat  # one slot as a note value (16 = sixteenth)
    n_bars = (max(grid) // slots_per_bar + 1) if grid else 1
    n_strings = len(inst.tuning)

    song = gp.Song(title=title, tempo=int(round(bpm)))
    track = song.tracks[0]
    track.name = inst.name.capitalize()
    track.fretCount = 24
    track.strings = [gp.GuitarString(n_strings - i, p) for i, p in enumerate(inst.tuning)]
    track.strings.sort(key=lambda s: s.number)
    track.channel.instrument = MIDI_PROGRAMS.get(inst.name, 25)

    bar_ticks = gp.Duration.quarterTime * beats_per_bar
    for bar in range(n_bars):
        if bar > 0:
            song.newMeasure()
        header = song.measureHeaders[bar]
        header.number = bar + 1
        header.start = gp.Duration.quarterTime + bar * bar_ticks
        header.timeSignature.numerator = beats_per_bar
        header.timeSignature.denominator.value = 4
        _fill_measure(track.measures[bar].voices[0], grid, bar * slots_per_bar, slots_per_bar, slot_value, n_strings)

    path.parent.mkdir(parents=True, exist_ok=True)
    gp.write(song, str(path), version=GP_VERSION)
    return path
