import tomllib
from pathlib import Path

from cyclopts import App

from cvf.proceedings_stamper.config import ProceedingsConfig

app = App()


@app.command
def main(config_path: Path):
    with open(config_path, "rb") as f:
        config = ProceedingsConfig.model_validate(tomllib.load(f))

    print(config)
