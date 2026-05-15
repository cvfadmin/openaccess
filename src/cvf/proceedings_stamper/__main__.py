import base64
import io
import tomllib
from pathlib import Path
from typing import Annotated

import multiprocess
from cyclopts import App, Parameter
from jinja2 import Environment, PackageLoader, select_autoescape
from PIL import Image
from tqdm.rich import tqdm

from cvf.proceedings_stamper.config import ProceedingsConfig
from cvf.proceedings_stamper.img import beside, crop, hcat, vcat  # noqa: F401
from cvf.proceedings_stamper.paper_list import PaperList
from cvf.proceedings_stamper.pdf_io import pdf_to_rgb  # noqa: F401

app = App()


def _stamp_paper(job):
    (paper, config) = job
    paper.stamp(config)
    return True, paper


@app.command
def stamp(
    config_path: Path,
    limit: int | None = 1,
    jobs: Annotated[int, Parameter(name=["--jobs", "-j"])] = 1,
    overwrite_existing: Annotated[
        bool, Parameter(name=["--overwrite-existing", "-f"])
    ] = False,
    match_output_name: Annotated[
        str | None,
        Parameter(
            name=["--match-output-name", "-S"],
            help="Only stamp for papers whose output filename contains this string",
        ),
    ] = None,
):
    with open(config_path, "rb") as f:
        config = ProceedingsConfig.model_validate(tomllib.load(f))

        papers = PaperList.read_paper_list(config)

    selected_papers = papers.papers if limit is None else papers.papers[:limit]
    if match_output_name is not None:
        selected_papers = [
            paper
            for paper in selected_papers
            if match_output_name in str(paper.output_path)
        ]

    N = len(selected_papers)
    if not overwrite_existing:
        selected_papers = [
            paper for paper in selected_papers if not paper.output_path.exists()
        ]
        print(
            f"Skipped {N - len(selected_papers)} papers that already exist. Use -f to overwrite them."
        )

    # selected_papers = multiprocess.Pool(jobs).imap_unordered(
    #     _stamp_paper,
    #     [(paper, config) for paper in selected_papers],
    # )
    # for result, paper in tqdm(selected_papers, unit="paper", total=N):
    for paper in selected_papers:
        print(paper)
        paper.stamp(config)


@app.command
def to_json(config_path: Path):
    """Print the paper list parsed from the spreadsheet in the config file as JSON."""
    with open(config_path, "rb") as f:
        config = ProceedingsConfig.model_validate(tomllib.load(f))

        papers = PaperList.read_paper_list(config)
    print(papers.model_dump_json(indent=2))


@app.command
def pprint(config_path: Path):
    """Print the paper list parsed from the spreadsheet in the config file."""
    with open(config_path, "rb") as f:
        config = ProceedingsConfig.model_validate(tomllib.load(f))

        papers = PaperList.read_paper_list(config)
    print(papers.model_dump_json(indent=2))


@app.command
def shell(config_path: Path):
    """Start IPython with papers loaded"""
    with open(config_path, "rb") as f:
        config = ProceedingsConfig.model_validate(tomllib.load(f))
        papers = PaperList.read_paper_list(config)

    from IPython.terminal.embed import InteractiveShellEmbed

    ipshell = InteractiveShellEmbed()
    ipshell.user_global_ns.update(globals())
    ipshell.user_ns.update(locals())
    ipshell.run_cell("import rich.pretty; rich.pretty.install()")
    ipshell.run_cell("%load_ext autoreload")
    ipshell.run_cell("%autoreload 2")
    ipshell(
        header="Useful variables: config, papers\nImage processing: pdf_to_rgb, crop, hcat, vcat"
    )


@app.command
def to_report(
    config_path: Path,
    limit: int | None = None,
    jobs: int = 8,
):
    """Convert all papers to PNG images and save them to the specified output directory."""
    with open(config_path, "rb") as f:
        config = ProceedingsConfig.model_validate(tomllib.load(f))

        papers = PaperList.read_paper_list(config)

    papers = papers[:limit]

    env = Environment(
        loader=PackageLoader("cvf.proceedings_stamper"),
        autoescape=select_autoescape(),
    )

    def _show_image(pil_image):
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        data = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"<img src='data:image/png;base64,{data}' />"

    env.filters["show"] = _show_image

    def render_pagenumber_tiles(job):
        # return job[0], hcat(job[1].image(dpi=24))
        return (
            job[0],
            hcat(
                crop(
                    job[1].image(),
                    width_inches=1,
                    height_inches=1,
                    anchor="bottom_center",
                )
            ),
            hcat(job[1].image(dpi=24)),
        )

    template = env.get_template("report_template.jinja2")
    with open(config.report_output_path, "w") as f:
        print(f"Wrote {config.report_output_path}")
        print(f"{f.tell() / 1024 / 1024} MB")

        N = len(papers)
        result_images = multiprocess.Pool(jobs).imap_unordered(
            render_pagenumber_tiles,
            enumerate(papers),
        )
        for i, pagenumber_tile, page_tile in tqdm(result_images, total=N, unit="paper"):
            papers[i].pagenumber_tile = pagenumber_tile
            papers[i].page_tile = page_tile

        f.write(template.render(papers=papers))
