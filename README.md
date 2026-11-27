# tune-to-tab

Takes an audio track, separates the instruments and generates **guitar** and **bass** tabs in separate files, as plain text and PDF.

## How it works

1. **Separation**: [Demucs](https://github.com/facebookresearch/demucs) `htdemucs_6s` splits the mix into 6 stems (drums, bass, other, vocals, guitar, piano). The `guitar` and `bass` stems are kept.
2. **Transcription**: Spotify's [basic-pitch](https://github.com/spotify/basic-pitch) turns each stem into notes (pitch + timing), limited to the instrument's frequency range. It also saves a MIDI file.
3. **Tempo**: `librosa` estimates the BPM and first beat from the original mix, so notes can be quantised to a sixteenth-note grid.
4. **Fingering**: every possible string/fret combination is computed for each note or chord. A Viterbi search picks the sequence that minimises hand movement, penalising stretches wider than 4 frets and high positions.
5. **Rendering**: ASCII tab, 4 bars per line, then exported to a landscape A4 PDF in a monospaced font. A tab system is never split across pages.

## Installation

Requires [uv](https://docs.astral.sh/uv/) and Python 3.10 or 3.11 (basic-pitch does not support newer versions).

```bash
uv sync
```

The Demucs weights (~80 MB) are downloaded on first run.

## Usage

```bash
uv run tune-to-tab song.wav
```

Output goes to `output/<track-name>/`:

```
guitar_tab.txt   # guitar tab, plain text
guitar_tab.pdf   # guitar tab, PDF
bass_tab.txt     # bass tab, plain text
bass_tab.pdf     # bass tab, PDF
guitar.mid       # raw MIDI transcription
bass.mid
stems/guitar.wav # separated stems
stems/bass.wav
```

Options:

| Option | Description |
|---|---|
| `-o DIR` | output directory (default `output`) |
| `-i guitar` / `-i bass` | extract a single instrument |
| `-f pdf` / `-f txt` | write only one tab format (default: both) |
| `--bpm 96` | force the BPM when the estimate is wrong (it is often off by half or double) |
| `--subdivisions 2` | eighth-note grid instead of sixteenths |
| `--bars-per-line 2` | fewer bars per line, larger font in the PDF |
| `--skip-separation` | reuse stems already computed and redo only transcription and tabs |
| `--device cuda` | run Demucs on the GPU |

Audio formats: WAV and FLAC always work. For MP3/M4A, install `ffmpeg` (`sudo apt install ffmpeg`).

## Example output

```
e|0-------5-------7-------5-------|3-------0-------------0-------3-|
B|--------------------------------|----------------3---------------|
G|--------------------------------|--------------------------------|
D|--------------------------------|--------------------------------|
A|--------------------------------|--------------------------------|
E|--------------------------------|--------------------------------|
```

## Limitations

- Automatic transcription is approximate. Dense mixes, heavy distortion or very full chords produce missing or spurious notes, so treat the output as a draft to refine.
- Fixed standard tuning (guitar EADGBE, 4-string bass EADG).
- Bass is treated as monophonic: when several notes sound together, the lowest is kept.
- No durations, bends, slides or hammer-ons: only note onsets.
- A wrong BPM estimate shifts the grid. Use `--bpm` to fix it.

## Project layout

| File | Role |
|---|---|
| [src/tune_to_tab/cli.py](src/tune_to_tab/cli.py) | command-line entry point, runs the pipeline |
| [src/tune_to_tab/separate.py](src/tune_to_tab/separate.py) | Demucs source separation |
| [src/tune_to_tab/transcribe.py](src/tune_to_tab/transcribe.py) | basic-pitch transcription and tempo estimation |
| [src/tune_to_tab/tab.py](src/tune_to_tab/tab.py) | fingering assignment and ASCII rendering (no audio dependencies) |
| [src/tune_to_tab/pdf.py](src/tune_to_tab/pdf.py) | PDF export |

## Tests

```bash
uv run pytest
```

The tests cover fingering, rendering and PDF export, which do not depend on the audio models.
