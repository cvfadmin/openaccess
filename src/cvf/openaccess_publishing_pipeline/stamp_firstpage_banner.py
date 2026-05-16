import io
from functools import cache
from typing import NamedTuple

from pikepdf import Page, Pdf
from reportlab.pdfgen import canvas

from cvf.openaccess_publishing_pipeline.config import BannerConfig

BANNER_WIDTH = 515.0
BANNER_HEIGHT = 34.0
BANNER_TOP_MARGIN = 3.0
BANNER_SIDE_MARGIN = 24.0

LOGO_PATH_SOURCE_X = 48.406
LOGO_PATH_SOURCE_Y = 3.066

TEXT_BASELINE_CENTER_Y = 19.1
TEXT_BASELINE_SPAN = 23.4
TEXT_LINE_HEIGHT = 11.7
TEXT_FONT = "Times-Roman"
TEXT_SIZE = 9.34

_BANNER_ALPHA = 0.5
_LOGO_BLUE = (0.447059, 0.576471, 0.772549)


class BannerGeometry(NamedTuple):
    x: float
    top: float
    width: float
    height: float
    text_center_x: float

    @property
    def bottom(self) -> float:
        return self.top - self.height


def make_banner_for_page(page: Page, config: BannerConfig):
    """Make a page-sized transparent PDF overlay containing the first-page banner."""
    page_width = float(page.mediabox[2]) - float(page.mediabox[0])
    page_height = float(page.mediabox[3]) - float(page.mediabox[1])
    return _generate_banner(page_width, page_height, tuple(config.text))


@cache
def _generate_banner(page_width: float, page_height: float, lines: tuple[str, ...]):
    content = io.BytesIO()
    c = canvas.Canvas(content, pagesize=(page_width, page_height), pdfVersion=(1, 4))

    geometry = _banner_geometry(page_width, page_height)

    c.setFillColorRGB(1, 1, 1)
    c.rect(
        geometry.x,
        geometry.bottom,
        geometry.width,
        geometry.height,
        fill=True,
        stroke=False,
    )

    c.saveState()
    c.setFillAlpha(_BANNER_ALPHA)
    c.setFillColorRGB(*_LOGO_BLUE)
    _draw_cvf_logo(c, geometry.x, geometry.top)
    c.restoreState()

    c.saveState()
    c.setFillAlpha(_BANNER_ALPHA)
    c.setFillColorRGB(0, 0, 0)
    text_size, line_height, first_baseline = _text_layout(lines)
    c.setFont(TEXT_FONT, text_size)
    for index, line in enumerate(lines):
        c.drawCentredString(
            geometry.text_center_x,
            geometry.top - first_baseline - index * line_height,
            line,
        )
    c.restoreState()

    c.showPage()
    c.save()
    content.seek(0)
    return Pdf.open(content)


def _banner_geometry(page_width: float, page_height: float) -> BannerGeometry:
    width = min(BANNER_WIDTH, page_width - 2 * BANNER_SIDE_MARGIN)
    x = (page_width - width) / 2.0
    top = page_height - BANNER_TOP_MARGIN
    return BannerGeometry(
        x=x,
        top=top,
        width=width,
        height=BANNER_HEIGHT,
        text_center_x=page_width / 2.0,
    )


def _text_layout(lines: tuple[str, ...]) -> tuple[float, float, float]:
    line_count = len(lines)
    if line_count <= 1:
        return TEXT_SIZE, TEXT_LINE_HEIGHT, TEXT_BASELINE_CENTER_Y

    line_height = min(
        TEXT_LINE_HEIGHT,
        TEXT_BASELINE_SPAN / (line_count - 1),
    )
    text_size = TEXT_SIZE * line_height / TEXT_LINE_HEIGHT
    first_baseline = TEXT_BASELINE_CENTER_Y - ((line_count - 1) * line_height / 2.0)
    return text_size, line_height, first_baseline


def _draw_cvf_logo(c: canvas.Canvas, banner_x: float, banner_top: float):
    def x(source_x: float) -> float:
        return banner_x + source_x - LOGO_PATH_SOURCE_X

    def y(top_down_y: float) -> float:
        return banner_top - (top_down_y - LOGO_PATH_SOURCE_Y)

    path = c.beginPath()
    path.moveTo(x(77.262), y(5.789))
    path.curveTo(
        x(71.715),
        y(5.789),
        x(67.215),
        y(10.68),
        x(67.215),
        y(16.707),
    )
    path.curveTo(
        x(67.215),
        y(22.738),
        x(71.715),
        y(27.625),
        x(77.262),
        y(27.625),
    )
    path.curveTo(
        x(78.852),
        y(27.625),
        x(80.355),
        y(27.223),
        x(81.691),
        y(26.508),
    )
    path.lineTo(x(79.777), y(22.742))
    path.curveTo(
        x(79.008),
        y(23.121),
        x(78.16),
        y(23.332),
        x(77.262),
        y(23.332),
    )
    path.curveTo(
        x(73.895),
        y(23.332),
        x(71.164),
        y(20.363),
        x(71.164),
        y(16.707),
    )
    path.curveTo(
        x(71.164),
        y(13.051),
        x(73.895),
        y(10.082),
        x(77.262),
        y(10.082),
    )
    path.curveTo(
        x(78.598),
        y(10.082),
        x(79.828),
        y(10.555),
        x(80.832),
        y(11.348),
    )
    path.lineTo(x(83.789), y(8.402))
    path.curveTo(
        x(82.031),
        y(6.77),
        x(79.75),
        y(5.789),
        x(77.262),
        y(5.789),
    )
    path.close()
    c.drawPath(path, fill=True, stroke=False)

    path = c.beginPath()
    path.moveTo(x(78.059), y(15.016))
    path.lineTo(x(87.273), y(33.801))
    path.lineTo(x(95.863), y(15.016))
    path.lineTo(x(91.531), y(15.016))
    path.lineTo(x(87.273), y(24.305))
    path.lineTo(x(82.684), y(15.016))
    path.close()
    c.drawPath(path, fill=True, stroke=False)

    path = c.beginPath()
    path.moveTo(x(96.422), y(5.812))
    path.lineTo(x(109.984), y(5.812))
    path.lineTo(x(109.984), y(9.465))
    path.lineTo(x(100.875), y(9.465))
    path.lineTo(x(100.875), y(14.996))
    path.lineTo(x(105.816), y(14.996))
    path.lineTo(x(105.816), y(18.547))
    path.lineTo(x(100.875), y(18.547))
    path.lineTo(x(100.875), y(27.707))
    path.lineTo(x(96.449), y(27.707))
    path.close()
    c.drawPath(path, fill=True, stroke=False)
