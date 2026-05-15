import io
from functools import cache
from pathlib import Path

from pikepdf import Page, Pdf
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

from cvf.proceedings_stamper.config import BannerConfig


def make_banner_for_page(page: Page, config: BannerConfig):
    """Make a pikepdf.Page showing the banner suitable for applying to a different pikepdf.Page."""
    height_inches = float(page.mediabox[3]) / 72.0
    height = f"{height_inches:0.1f}in"
    return _generate_banner(
        _banner_template_path(config.input_path, height),
        tuple(config.text),
    )


def _banner_template_path(input_path: Path, height: str) -> str:
    if input_path.is_dir():
        return str(input_path / f"template-{height}.svg")
    return str(input_path).format(height=height)


@cache
def _generate_banner(in_fname, lines):
    """
    Doctor the SVG template by replacing LINE1, LINE2, and LINE3 with the actual banner text, then render the SVG to PDF and return a PikePDF "Pdf" instance.
    """
    with open(in_fname, "rb") as f_in:
        in_buf = f_in.read().decode("utf-8")
        for i, line in enumerate(lines, start=1):
            assert f"LINE{i}" in in_buf
            in_buf = in_buf.replace(f"LINE{i}", line)
        assert f"LINE{i + 1}" not in in_buf
        drawing = svg2rlg(io.BytesIO(in_buf.encode("utf-8")))
        out_buf = renderPDF.drawToString(drawing)
        return Pdf.open(io.BytesIO(out_buf))
