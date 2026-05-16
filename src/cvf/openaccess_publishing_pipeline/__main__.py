import base64
import io
import os
import sys
from pathlib import Path

os.environ.setdefault("PYDANTIC_ERRORS_INCLUDE_URL", "0")
from typing import Annotated

import multiprocess
from cyclopts import App, Parameter
from jinja2 import Environment, PackageLoader
from PIL import Image
from rich import print as rprint
from tqdm.rich import tqdm

from cvf.openaccess_publishing_pipeline.config import ProceedingsConfig
from cvf.openaccess_publishing_pipeline.img import (  # noqa: F401
    beside,
    crop,
    hcat,
    vcat,
)
from cvf.openaccess_publishing_pipeline.paper import emit_csv
from cvf.openaccess_publishing_pipeline.paper_list import PaperList
from cvf.openaccess_publishing_pipeline.pdf_io import (  # noqa: F401
    nice_open_pdf_file,
    pdf_to_rgb,
)
from cvf.openaccess_publishing_pipeline.report import generate_report

app = App(help_on_error=True)


def _stamp_paper(job):
    (paper, config) = job
    try:
        paper.stamp(config)
        return True, paper, None
    except Exception as exc:
        return False, paper, exc


@app.command(alias="run")
def stamp(
    config_path: Path,
    *,
    limit: Annotated[
        int | None,
        Parameter(name=["--limit", "-l"], help="Only process the first N papers"),
    ] = None,
    jobs: Annotated[
        int, Parameter(name=["--jobs", "-j"], help="Number of jobs to run in parallel")
    ] = 8,
    match_output_name: Annotated[
        str | None,
        Parameter(
            name=["--match-output-name", "-S"],
            help="Only stamp for papers whose output filename contains this string",
        ),
    ] = None,
    csv: Annotated[bool, Parameter(help="Add papers.csv after stamping")] = True,
    report: Annotated[bool, Parameter(help="Generate report after stamping")] = True,
    dry_run: Annotated[
        bool,
        Parameter(
            name=["--dry-run", "-n"],
            help="Print papers that would be stamped without writing any output",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        Parameter(
            name=["--overwrite", "-f"],
            help="Re-stamp papers whose output files already exist (default: skip them)",
        ),
    ] = False,
):
    "Stamp all papers from the config file. See '--help' for options about limiting, parallelization, etc."
    config = ProceedingsConfig.from_toml(config_path)
    papers = PaperList.read_paper_list(config)

    selected_papers = papers.papers

    if match_output_name is not None:
        selected_papers = [
            paper
            for paper in selected_papers
            if match_output_name in str(paper.output_path)
        ]
    if not overwrite:
        selected_papers = [p for p in selected_papers if not p.output_path.exists()]

    if limit is not None:
        selected_papers = selected_papers[:limit]

    N = len(selected_papers)

    if dry_run:
        for paper in selected_papers:
            print(paper.output_path)
        print(f"\n{N} paper(s) would be stamped.")
        return

    selected_papers = multiprocess.Pool(jobs).imap_unordered(
        _stamp_paper,
        [(paper, config) for paper in selected_papers],
    )
    failures = []
    for success, paper, exc in tqdm(
        selected_papers, unit="paper", total=N, desc="Stamping papers"
    ):
        if success:
            print(paper)
        else:
            failures.append((paper, exc))
            print(f"FAILED: {paper} — {exc}")

    if failures:
        rprint(f"\n[bold white on red]{len(failures)} paper(s) failed:")
        for paper, exc in failures:
            rprint(f"[red]{paper.output_path}[/red]\n{exc!r}")
        rprint(
            "\nCVF note: you can use '-S' to only re-run failed papers, or debug further with the 'shell' command. See '--help' for details."
        )
        sys.exit(1)

    if csv:
        write_csv(config_path)
    if report:
        if match_output_name is not None:
            print(
                "Skipping report generation because --match-output-name / -S was used."
            )
        else:
            write_report(config_path, limit=limit, jobs=jobs)


@app.command
def write_csv(config_path: Path):
    "Save a paper list to output/papers.json. Run automatically as part of 'stamp'."
    config = ProceedingsConfig.from_toml(config_path)
    papers = PaperList.read_paper_list(config)
    emit_csv(papers, config)


@app.command
def verify(config_path: Path):
    "Check that all output files exist, have the correct page count, and that papers.csv exists."
    config = ProceedingsConfig.from_toml(config_path)
    papers = PaperList.read_paper_list(config)

    errors = []

    csv_path = config.output_path / config.csv_output_path
    if not csv_path.exists():
        errors.append(f"Missing papers.csv: {csv_path}")

    for paper in papers.papers:
        if not paper.output_path.exists():
            errors.append(f"Missing output: {paper.output_path}")
            continue
        try:
            with nice_open_pdf_file(paper.output_path) as pdf:
                actual = len(pdf.pages)
            if paper.start_page is not None and paper.last_page is not None:
                expected = paper.last_page - paper.start_page + 1
                if actual != expected:
                    errors.append(
                        f"Wrong page count for {paper.output_path}: expected {expected}, got {actual}"
                    )
        except Exception as exc:
            errors.append(f"Could not open {paper.output_path}: {exc}")

    if errors:
        for err in errors:
            print(err)
        print(f"\n{len(errors)} error(s) found.")
        sys.exit(1)
    else:
        print(f"All OK ({len(papers.papers)} papers, csv at {csv_path})")


@app.command
def show_json(config_path: Path):
    """Print a paper list as JSON."""
    config = ProceedingsConfig.from_toml(config_path)
    papers = PaperList.read_paper_list(config)
    print(papers.model_dump_json(indent=2))


@app.command
def shell(config_path: Path):
    """Start an IPython shell with a paper list loaded."""
    config = ProceedingsConfig.from_toml(config_path)
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
def write_report(
    config_path: Path,
    *,
    limit: Annotated[
        int | None,
        Parameter(name=["--limit", "-n"], help="Only process the first N papers"),
    ] = None,
    jobs: Annotated[
        int, Parameter(name=["--jobs", "-j"], help="Number of jobs to run in parallel")
    ] = 8,
    group_size: int = 300,
):
    """Generate a paper list report used for quality assurance. Run automatically as part of 'stamp'."""
    config = ProceedingsConfig.from_toml(config_path)
    papers = PaperList.read_paper_list(config)

    papers = papers[:limit]

    n_groups = (len(papers) + group_size - 1) // group_size
    for group_num, i in enumerate(range(0, len(papers), group_size)):
        group = papers[i : i + group_size]
        group_name = config.report_output_path.with_stem(
            f"{config.report_output_path.stem}-{group_num + 1:05d}-of-{n_groups:05d}"
        )
        if group_num < n_groups - 1:
            next_group_name = config.report_output_path.with_stem(
                f"{config.report_output_path.stem}-{group_num + 2:05d}-of-{n_groups:05d}"
            )
        else:
            next_group_name = None
        report = generate_report(papers=group, next_filename=next_group_name, jobs=jobs)
        group_name.parent.mkdir(exist_ok=True, parents=True)
        group_name.write_text(report)
        print(f"Wrote {group_name} ({len(group)} papers)")
        print(f"{group_name.stat().st_size / 1024 / 1024} MB")
