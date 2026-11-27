from tune_to_tab.pdf import tab_to_pdf
from tune_to_tab.tab import GUITAR, Note, assign_positions, render_tab


def test_tab_to_pdf_writes_a_pdf(tmp_path):
    notes = [Note(i * 0.5, i * 0.5 + 0.4, 40 + i) for i in range(64)]
    text = render_tab(assign_positions(notes, GUITAR), GUITAR, bpm=120, title="demo - guitar")
    out = tab_to_pdf(text, tmp_path / "guitar_tab.pdf")
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 1000
