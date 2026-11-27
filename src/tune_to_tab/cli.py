"""tune-to-tab: audio track -> guitar and bass tabs in separate files."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from .tab import BASS, GUITAR, Instrument, assign_positions, render_tab

INSTRUMENTS: dict[str, Instrument] = {"guitar": GUITAR, "bass": BASS}
FORMATS = ("txt", "pdf", "gp")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="tune-to-tab", description=__doc__)
    p.add_argument("audio", type=Path, help="input audio file (wav, flac, mp3, ...)")
    p.add_argument("-o", "--output", type=Path, default=Path("output"), help="output directory (default: ./output)")
    p.add_argument(
        "-i", "--instruments", nargs="+", choices=sorted(INSTRUMENTS), default=["guitar", "bass"],
        help="instruments to extract (default: guitar bass)",
    )
    p.add_argument(
        "-f", "--formats", nargs="+", choices=FORMATS, default=list(FORMATS),
        help="tab output formats: txt, pdf, gp (Guitar Pro 5) (default: all)",
    )
    p.add_argument("--bpm", type=float, help="force the BPM instead of estimating it")
    p.add_argument("--subdivisions", type=int, default=4, help="columns per beat (4 = sixteenth notes; must be a power of two for gp)")
    p.add_argument("--bars-per-line", type=int, default=4)
    p.add_argument("--device", help="cpu or cuda (default: automatic)")
    p.add_argument("--skip-separation", action="store_true", help="reuse stems already in the output directory")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    from .gp import tab_to_gp
    from .pdf import tab_to_pdf
    from .separate import separate
    from .transcribe import estimate_tempo, transcribe

    if not args.audio.exists():
        raise SystemExit(f"File not found: {args.audio}")

    song_dir = args.output / args.audio.stem
    stems_dir = song_dir / "stems"

    if args.skip_separation:
        stems = {name: stems_dir / f"{name}.wav" for name in args.instruments}
        missing = [str(p) for p in stems.values() if not p.exists()]
        if missing:
            raise SystemExit(f"Missing stems: {missing}")
    else:
        print(f"[1/3] Separating instruments with Demucs -> {stems_dir}")
        stems = separate(args.audio, stems_dir, stems=tuple(args.instruments), device=args.device)

    if args.bpm:
        bpm, offset = args.bpm, 0.0
    else:
        bpm, offset = estimate_tempo(args.audio)
    print(f"[2/3] Tempo: ~{bpm:.1f} BPM")

    for name in args.instruments:
        inst = INSTRUMENTS[name]
        print(f"[3/3] Transcribing {name}...")
        notes = transcribe(stems[name], inst, midi_out=song_dir / f"{name}.mid")
        notes = [replace(n, start=max(0.0, n.start - offset), end=max(0.0, n.end - offset)) for n in notes]
        events = assign_positions(notes, inst)
        text = render_tab(
            events, inst, bpm=bpm, subdivisions_per_beat=args.subdivisions,
            bars_per_line=args.bars_per_line, title=f"{args.audio.stem} - {name}",
        )
        written = []
        if "txt" in args.formats:
            txt_path = song_dir / f"{name}_tab.txt"
            txt_path.write_text(text, encoding="utf-8")
            written.append(txt_path)
        if "pdf" in args.formats:
            written.append(tab_to_pdf(text, song_dir / f"{name}_tab.pdf"))
        if "gp" in args.formats:
            written.append(
                tab_to_gp(
                    events, inst, bpm=bpm, path=song_dir / f"{name}_tab.gp5",
                    subdivisions_per_beat=args.subdivisions, title=f"{args.audio.stem} - {name}",
                )
            )
        print(f"      {len(notes)} notes, {len(events)} events -> {', '.join(map(str, written))}")


if __name__ == "__main__":
    main()
