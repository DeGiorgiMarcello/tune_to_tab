"""Export of an ASCII tab to PDF, using a monospaced font so columns stay aligned."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

MARGIN_MM = 12
MAX_FONT_PT = 10
MIN_FONT_PT = 5
# Courier glyphs are 0.6 em wide; 1 pt = 0.3528 mm
CHAR_WIDTH_EM = 0.6
PT_TO_MM = 0.3528


def _fit_font_size(longest_line: int, usable_width_mm: float) -> float:
    if longest_line == 0:
        return MAX_FONT_PT
    size = usable_width_mm / (longest_line * CHAR_WIDTH_EM * PT_TO_MM)
    return max(MIN_FONT_PT, min(MAX_FONT_PT, size))


def tab_to_pdf(text: str, path: Path) -> Path:
    """Write the tab text to a landscape A4 PDF.

    The first line is used as the title. Blocks separated by blank lines (one tab
    system each) are never split across pages.
    """
    lines = text.splitlines()
    title, body = (lines[0], lines[1:]) if lines else ("", [])

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_margins(MARGIN_MM, MARGIN_MM, MARGIN_MM)
    pdf.set_auto_page_break(False)
    pdf.add_page()

    usable_w = pdf.w - 2 * MARGIN_MM
    font_pt = _fit_font_size(max((len(line) for line in body), default=0), usable_w)
    line_h = font_pt * PT_TO_MM * 1.25

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Split the body into blocks separated by blank lines.
    blocks: list[list[str]] = [[]]
    for line in body:
        if line.strip():
            blocks[-1].append(line)
        elif blocks[-1]:
            blocks.append([])
    blocks = [b for b in blocks if b]

    pdf.set_font("Courier", "", font_pt)
    bottom = pdf.h - MARGIN_MM
    for block in blocks:
        block_h = (len(block) + 1) * line_h
        if pdf.get_y() + block_h > bottom:
            pdf.add_page()
        for line in block:
            pdf.cell(0, line_h, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(line_h)

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    return path
