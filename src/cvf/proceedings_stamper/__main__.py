import tomllib
from pathlib import Path

from cyclopts import App

from cvf.proceedings_stamper.config import ProceedingsConfig
from cvf.proceedings_stamper.paper_list import PaperList

app = App()


@app.command
def main(config_path: Path):
    with open(config_path, "rb") as f:
        config = ProceedingsConfig.model_validate(tomllib.load(f))

        papers = PaperList.read_paper_list(config)

    print(config)
    print(papers)
