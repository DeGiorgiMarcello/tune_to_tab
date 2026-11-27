"""Source separation with Demucs (6-stem model: includes guitar and bass)."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch

DEFAULT_MODEL = "htdemucs_6s"  # stems: drums, bass, other, vocals, guitar, piano


def separate(
    audio_path: Path,
    out_dir: Path,
    stems: tuple[str, ...] = ("guitar", "bass"),
    model_name: str = DEFAULT_MODEL,
    device: str | None = None,
) -> dict[str, Path]:
    """Separate the track and save the requested stems as WAV. Returns {stem: path}."""
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = get_model(model_name)
    model.eval()

    missing = [s for s in stems if s not in model.sources]
    if missing:
        raise ValueError(f"Model {model_name} does not produce stems {missing} (available: {model.sources})")

    # librosa reads via soundfile/audioread: WAV/FLAC/OGG always, MP3 with libsndfile >= 1.1 or ffmpeg
    wav, _ = librosa.load(str(audio_path), sr=model.samplerate, mono=False)
    if wav.ndim == 1:
        wav = np.stack([wav, wav])
    wav = torch.from_numpy(wav[: model.audio_channels]).float()

    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    mix = ((wav - mean) / std).unsqueeze(0)

    with torch.no_grad():
        sources = apply_model(model, mix, device=device, split=True, overlap=0.25, progress=True)[0]
    sources = sources * std + mean

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for stem in stems:
        data = sources[model.sources.index(stem)].cpu().numpy().T
        path = out_dir / f"{stem}.wav"
        sf.write(path, data, model.samplerate)
        paths[stem] = path
    return paths
