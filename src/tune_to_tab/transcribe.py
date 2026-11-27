"""Audio-to-notes transcription with Spotify basic-pitch, plus tempo estimation."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

from .tab import Instrument, Note


def transcribe(stem_path: Path, inst: Instrument, midi_out: Path | None = None) -> list[Note]:
    """Extract notes from the stem, restricting frequencies to the instrument's range."""
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict

    _, midi_data, note_events = predict(
        str(stem_path),
        ICASSP_2022_MODEL_PATH,
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_length=80,  # ms: drops spurious very short notes
        minimum_frequency=float(librosa.midi_to_hz(inst.lowest - 1)),
        maximum_frequency=float(librosa.midi_to_hz(inst.highest + 1)),
        melodia_trick=True,
    )
    if midi_out is not None:
        midi_data.write(str(midi_out))
    return [Note(float(s), float(e), int(p), float(a)) for s, e, p, a, _ in note_events]


def estimate_tempo(audio_path: Path) -> tuple[float, float]:
    """Return (bpm, offset_seconds), where offset is the position of the first beat."""
    y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0]) or 120.0
    beat_times = librosa.frames_to_time(beats, sr=sr)
    offset = float(beat_times[0] % (60.0 / bpm)) if len(beat_times) else 0.0
    return bpm, offset
