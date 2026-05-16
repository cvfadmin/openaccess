import base64
import io
import secrets
import tomllib
from pathlib import Path
from typing import Annotated, Literal

from cyclopts import App, Parameter
from jinja2 import Environment, PackageLoader, select_autoescape
from multiprocess import Pool
from PIL import Image
from tqdm.rich import tqdm

from cvf.proceedings_stamper.config import ProceedingsConfig
from cvf.proceedings_stamper.img import beside, crop, hcat, vcat  # noqa: F401
from cvf.proceedings_stamper.paper import Paper
from cvf.proceedings_stamper.paper_list import PaperList
from cvf.proceedings_stamper.pdf_io import pdf_to_rgb  # noqa: F401


class DeferredTemplateRenderer:
    def __init__(self):
        self.closures = {}

    def make_jinja_filter(self, fun):
        def _filter(*args, **kwargs):
            tag = secrets.token_hex(8)
            self.closures[tag] = lambda: fun(*args, **kwargs)
            return tag

        return _filter

    def resolve(self, template_str, jobs: int | None = None):
        pool = Pool(jobs)
        N = len(self.closures)
        results = pool.imap_unordered(
            lambda job: (job[0], job[1]()), self.closures.items()
        )
        for key, value in tqdm(results, total=N):
            template_str = template_str.replace(key, value)
        return template_str


def show(
    paper: Paper,
    width_inches: float | None = None,
    height_inches: float | None = None,
    anchor: Literal["top_center", "bottom_center"] = "bottom_center",
    format="WEBP",
    quality=100,
    dpi: int = 72,
    pages: Literal["first", "all"] = "all",
):
    image = paper.image(dpi=dpi, pages=pages)
    cropped = crop(
        image,
        width_inches=width_inches,
        height_inches=height_inches,
        anchor=anchor,
        dpi=dpi,
    )
    strip = hcat(cropped)
    buffer = io.BytesIO()
    strip.save(buffer, format=format, quality=quality)
    data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"<img src='data:image/{format.lower()};base64,{data}' />"


def generate_report(jobs: int | None = None, **kwargs):
    env = Environment(
        loader=PackageLoader("cvf.proceedings_stamper"),
        autoescape=select_autoescape(),
    )
    env.filters["str"] = str
    deferred_image_loader = DeferredTemplateRenderer()

    env.filters["show"] = deferred_image_loader.make_jinja_filter(show)

    template = env.get_template("report_template.jinja2")

    return deferred_image_loader.resolve(template.render(**kwargs), jobs=jobs)
