import tomllib
from pathlib import Path
from typing import Annotated

import multiprocess
from cyclopts import App, Parameter
from tqdm.rich import tqdm

from cvf.proceedings_stamper.config import ProceedingsConfig
from cvf.proceedings_stamper.paper_list import PaperList

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
):
    with open(config_path, "rb") as f:
        config = ProceedingsConfig.model_validate(tomllib.load(f))

        papers = PaperList.read_paper_list(config)

    selected_papers = papers.papers if limit is None else papers.papers[:limit]
    N = len(selected_papers)
    if not overwrite_existing:
        selected_papers = [
            paper for paper in selected_papers if not paper.output_path.exists()
        ]
        print(
            f"Skipped {N - len(selected_papers)} papers that already exist. Use -f to overwrite them."
        )

    print(selected_papers)
    if jobs > 1:
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


if __name__ == "__main__":
    app()
