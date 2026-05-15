import base64
import io
import tomllib
from pathlib import Path
from typing import Annotated

import multiprocess
from cyclopts import App, Parameter
from jinja2 import Environment, PackageLoader
from PIL import Image
from tqdm.rich import tqdm

from cvf.proceedings_stamper.config import ProceedingsConfig
from cvf.proceedings_stamper.img import beside, crop, hcat, vcat  # noqa: F401
from cvf.proceedings_stamper.paper_list import PaperList
from cvf.proceedings_stamper.pdf_io import pdf_to_rgb  # noqa: F401
from cvf.proceedings_stamper.report import generate_report

app = App()


def _stamp_paper(job):
    (paper, config) = job
    paper.stamp(config)
    return True, paper


@app.command
def stamp(
    config_path: Path,
    limit: int | None = None,
    jobs: Annotated[int, Parameter(name=["--jobs", "-j"])] = 8,
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

    selected_papers = papers.papers

    if match_output_name is not None:
        selected_papers = [
            paper
            for paper in selected_papers
            if match_output_name in str(paper.output_path)
        ]
    if limit is not None:
        selected_papers = selected_papers[:limit]

    N = len(selected_papers)

    selected_papers = multiprocess.Pool(jobs).imap_unordered(
        _stamp_paper,
        [(paper, config) for paper in selected_papers],
    )
    for result, paper in tqdm(selected_papers, unit="paper", total=N):
        print(paper)


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

    with open(config.report_output_path, "w") as f:
        f.write(generate_report(papers))

        print(f"Wrote {config.report_output_path}")
        print(f"{f.tell() / 1024 / 1024} MB")
