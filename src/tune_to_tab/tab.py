"""Conversion of notes (MIDI pitch + timing) into ASCII tablature.

Pure logic with no audio dependencies, so it can be tested in isolation.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

# Standard tunings, from the lowest string to the highest (MIDI numbers).
GUITAR_STANDARD = (40, 45, 50, 55, 59, 64)  # E2 A2 D3 G3 B3 E4
BASS_STANDARD = (28, 33, 38, 43)  # E1 A1 D2 G2

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


@dataclass(frozen=True)
class Note:
    start: float  # seconds
    end: float  # seconds
    pitch: int  # MIDI number
    velocity: float = 1.0


@dataclass(frozen=True)
class Instrument:
    name: str
    tuning: tuple[int, ...]
    max_fret: int
    max_polyphony: int  # max simultaneous notes to keep
    keep_lowest: bool  # when there are too many notes: keep the low ones (bass) or the high ones

    @property
    def lowest(self) -> int:
        return min(self.tuning)

    @property
    def highest(self) -> int:
        return max(self.tuning) + self.max_fret


GUITAR = Instrument("guitar", GUITAR_STANDARD, max_fret=22, max_polyphony=6, keep_lowest=False)
BASS = Instrument("bass", BASS_STANDARD, max_fret=20, max_polyphony=1, keep_lowest=True)


# (string_index, fret)
Position = tuple[int, int]


@dataclass(frozen=True)
class TabEvent:
    time: float
    positions: tuple[Position, ...]


def fold_into_range(pitch: int, inst: Instrument) -> int:
    """Shift notes outside the instrument's range by whole octaves."""
    while pitch < inst.lowest:
        pitch += 12
    while pitch > inst.highest:
        pitch -= 12
    return pitch


def group_chords(notes: list[Note], tolerance: float = 0.04) -> list[tuple[float, list[int]]]:
    """Group notes with near-simultaneous onsets into events (time, [pitch])."""
    groups: list[tuple[float, list[int]]] = []
    for note in sorted(notes, key=lambda n: (n.start, n.pitch)):
        if groups and note.start - groups[-1][0] <= tolerance:
            if note.pitch not in groups[-1][1]:
                groups[-1][1].append(note.pitch)
        else:
            groups.append((note.start, [note.pitch]))
    return groups


def candidate_fingerings(pitches: list[int], inst: Instrument) -> list[tuple[Position, ...]]:
    """Every way of playing the given notes on distinct strings."""
    options = []
    for p in pitches:
        opts = [
            (s, p - open_p)
            for s, open_p in enumerate(inst.tuning)
            if 0 <= p - open_p <= inst.max_fret
        ]
        options.append(opts)
    result = []
    for combo in itertools.product(*options):
        strings = [s for s, _ in combo]
        if len(set(strings)) == len(strings):
            result.append(tuple(sorted(combo)))
    return result


def _hand_position(fingering: tuple[Position, ...]) -> float | None:
    fretted = [f for _, f in fingering if f > 0]
    return sum(fretted) / len(fretted) if fretted else None


def _static_cost(fingering: tuple[Position, ...]) -> float:
    fretted = [f for _, f in fingering if f > 0]
    span = (max(fretted) - min(fretted)) if fretted else 0
    cost = 0.0
    if span > 4:
        cost += 50 * (span - 4)  # stretches the hand cannot reach
    cost += span * 1.5
    cost += sum(0.15 * f for _, f in fingering)  # prefer low positions
    return cost


def _transition_cost(a: tuple[Position, ...], b: tuple[Position, ...]) -> float:
    pa, pb = _hand_position(a), _hand_position(b)
    if pa is None or pb is None:
        return 0.0
    return abs(pa - pb)


def _reduce_polyphony(pitches: list[int], inst: Instrument) -> list[int]:
    pitches = sorted(set(pitches))
    if len(pitches) <= inst.max_polyphony:
        return pitches
    if inst.keep_lowest:
        return pitches[: inst.max_polyphony]
    return pitches[-inst.max_polyphony :]


def _playable_subset(pitches: list[int], inst: Instrument) -> list[tuple[Position, ...]]:
    """Drop notes from the chord until at least one fingering exists."""
    pitches = list(pitches)
    while pitches:
        cands = candidate_fingerings(pitches, inst)
        if cands:
            return cands
        # drop the least important note (lowest for guitar, highest for bass)
        pitches.pop(-1 if inst.keep_lowest else 0)
    return []


def assign_positions(notes: list[Note], inst: Instrument) -> list[TabEvent]:
    """Pick string/fret for each note, minimising hand movement (Viterbi)."""
    groups = group_chords(
        [Note(n.start, n.end, fold_into_range(n.pitch, inst), n.velocity) for n in notes]
    )
    times: list[float] = []
    layers: list[list[tuple[Position, ...]]] = []
    for t, pitches in groups:
        cands = _playable_subset(_reduce_polyphony(pitches, inst), inst)
        if cands:
            times.append(t)
            layers.append(cands)
    if not layers:
        return []

    # Viterbi
    cost = [_static_cost(c) for c in layers[0]]
    back: list[list[int]] = [[-1] * len(layers[0])]
    for i in range(1, len(layers)):
        new_cost, new_back = [], []
        for cand in layers[i]:
            sc = _static_cost(cand)
            best_j, best = min(
                ((j, cost[j] + _transition_cost(prev, cand)) for j, prev in enumerate(layers[i - 1])),
                key=lambda x: x[1],
            )
            new_cost.append(best + sc)
            new_back.append(best_j)
        cost, back = new_cost, back + [new_back]

    idx = min(range(len(cost)), key=cost.__getitem__)
    path = []
    for i in range(len(layers) - 1, -1, -1):
        path.append(layers[i][idx])
        idx = back[i][idx]
    path.reverse()
    return [TabEvent(t, p) for t, p in zip(times, path)]


def _string_label(open_pitch: int) -> str:
    return NOTE_NAMES[open_pitch % 12]


Grid = dict[int, dict[int, int]]  # slot -> {string_index: fret}


def quantize(events: list[TabEvent], bpm: float, subdivisions_per_beat: int = 4) -> Grid:
    """Snap events onto a rhythmic grid of `subdivisions_per_beat` slots per beat."""
    step = 60.0 / bpm / subdivisions_per_beat
    grid: Grid = {}
    for ev in events:
        slot = int(round(ev.time / step))
        cell = grid.setdefault(slot, {})
        for s, f in ev.positions:
            cell.setdefault(s, f)  # if two events land in the same slot, the first one wins
    return grid


def render_tab(
    events: list[TabEvent],
    inst: Instrument,
    bpm: float,
    subdivisions_per_beat: int = 4,
    beats_per_bar: int = 4,
    bars_per_line: int = 4,
    title: str | None = None,
) -> str:
    """Render the events as ASCII tab on a quantised rhythmic grid."""
    slots_per_bar = subdivisions_per_beat * beats_per_bar
    n_strings = len(inst.tuning)
    grid = quantize(events, bpm, subdivisions_per_beat)

    last_slot = max(grid) if grid else 0
    n_bars = last_slot // slots_per_bar + 1

    labels = [_string_label(p) for p in inst.tuning]
    # write the high E in lowercase, by convention
    if n_strings == 6 and labels[0] == labels[-1]:
        labels[-1] = labels[-1].lower()
    label_w = max(len(lbl) for lbl in labels)

    header = [
        title or inst.name.capitalize(),
        f"Tuning: {' '.join(NOTE_NAMES[p % 12] + str(p // 12 - 1) for p in inst.tuning)}"
        f" | BPM ~{bpm:.0f} | 1 column = 1/{subdivisions_per_beat * 4}",
        "",
    ]

    out_lines = list(header)
    for line_start in range(0, n_bars, bars_per_line):
        rows = [f"{lbl:<{label_w}}|" for lbl in labels]
        for bar in range(line_start, min(line_start + bars_per_line, n_bars)):
            for k in range(slots_per_bar):
                cell = grid.get(bar * slots_per_bar + k, {})
                width = max((len(str(f)) for f in cell.values()), default=1)
                for s in range(n_strings):
                    txt = str(cell[s]) if s in cell else ""
                    rows[s] += txt.ljust(width, "-") + "-"
            for s in range(n_strings):
                rows[s] += "|"
        # the highest string goes on top
        out_lines.extend(reversed(rows))
        out_lines.append(f"{'':<{label_w}} bars {line_start + 1}-{min(line_start + bars_per_line, n_bars)}")
        out_lines.append("")
    return "\n".join(out_lines)
