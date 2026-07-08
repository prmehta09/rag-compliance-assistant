"""Renders build_report()'s markdown output (see src/audit.py) as a PDF.

Uses fpdf2 - pure Python, no system-binary dependencies (no wkhtmltopdf, no
GTK/Pango) - so it installs the same way on Windows and on Render. Text is
set in a bundled Unicode font (DejaVu Sans, fonts/DejaVuSans.ttf - Bitstream
Vera license, see fonts/LICENSE) instead of fpdf2's built-in Latin-1-only
core fonts, because real report text routinely contains "§" (HIPAA
citations), em dashes, and curly quotes that core fonts can't render.

This module only knows how to typeset the SMALL, fixed markdown grammar
build_report() actually emits - headings (#/##/###), bullets (- ), blank
lines, and inline **bold** spans (used only in the "Needs Human Review"
summary bullets) - verified against real build_report() output, not assumed.
It does not know anything about audits or findings.
"""

from pathlib import Path

from fpdf import FPDF

FONTS_DIR = Path(__file__).resolve().parent / "fonts"


def markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(left=18, top=18, right=18)
    pdf.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_page()

    previous_blank = True  # suppress a leading gap before the very first line
    for raw_line in markdown_text.split("\n"):
        line = raw_line.rstrip()

        if not line:
            if not previous_blank:
                pdf.ln(3)
            previous_blank = True
            continue
        previous_blank = False

        if line.startswith("### "):
            pdf.set_font("DejaVu", "B", 12)
            pdf.ln(2)
            pdf.multi_cell(0, 7, line[4:], markdown=True, new_x="LMARGIN", new_y="NEXT")
        elif line.startswith("## "):
            pdf.set_font("DejaVu", "B", 14)
            pdf.ln(3)
            pdf.multi_cell(0, 8, line[3:], markdown=True, new_x="LMARGIN", new_y="NEXT")
        elif line.startswith("# "):
            pdf.set_font("DejaVu", "B", 18)
            pdf.multi_cell(0, 10, line[2:], markdown=True, new_x="LMARGIN", new_y="NEXT")
        elif line.startswith("- "):
            pdf.set_font("DejaVu", "", 10)
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(0, 6, f"-  {line[2:]}", markdown=True, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(0, 6, line, markdown=True, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
