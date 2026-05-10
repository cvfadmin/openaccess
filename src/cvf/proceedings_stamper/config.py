from pathlib import Path

from pandas.io.formats.console import in_interactive_session
from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator
from pydantic.types import DirectoryPath


class PaperListSpreadsheetColumnsConfig(BaseModel):
    "List of column names in the spreadsheet. These are used to extract the title and abstract of each paper, which are then used to generate the banner text."

    model_config = ConfigDict(use_attribute_docstrings=True)

    title: str
    "Column of the paper title."

    abstract: str
    "Column of the paper abstract."

    authors: str
    "Column of the paper authors."

    authors_separator: str
    "The string that separates the authors in the authors column. Usually ';' or ',' depending on the IEEE spreadsheet."


class PaperListSpreadsheetConfig(BaseModel):
    url: AnyUrl
    """URL to the spreadsheet in CSV format. For Google sheets, you can use the URL, see https://stackoverflow.com/questions/33713084/download-link-for-google-spreadsheets-csv-export-with-multiple-sheets"""

    columns: PaperListSpreadsheetColumnsConfig


class BannerConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    in_path: Path
    """Path to the SVG template for the banner. This path should contain the string "{height}" which will be replaced with the height of the page in inches, e.g. "banner_template_{height}.svg". This allows you to have different banner templates for different page heights, if needed. The SVG file itself should contain the strings "LINE1", "LINE2", and "LINE3" which will be replaced with the actual banner text. Note: Be sure that the needed fonts are installed on the system and that the SVG file references them correctly."""

    banner_text: tuple[str, str, str]
    """Three-line banner contents to be stamped at the top of the first page."""

    @field_validator("banner_text", mode="before")
    def validate_text(cls, v: str) -> tuple[str, str, str]:
        txt = v.strip().splitlines()
        if len(txt) != 3:
            raise ValueError(
                f"Banner text must be three lines. Got {len(txt)} lines. Raw: {txt!r}"
            )
        return tuple(txt)


class ProceedingsConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    acronym: str
    """Four-letter acronym for the conference."""

    year: int = Field(ge=1900, le=2500)
    """Year of the conference."""

    input_path: DirectoryPath
    """Path to the directory containing PDF."""

    output_path: Path
    """Path to output files."""

    zip_output_path: Path
    """Path to the output zip file."""

    spreadsheet: PaperListSpreadsheetConfig

    banner: BannerConfig

    @field_validator("acronym")
    def validate_ancronym(cls, v: str) -> str:
        if not v.isupper():
            raise ValueError("Ancronym must be uppercase, i.e.  'CVPR'")
        if not v.isalpha():
            raise ValueError("Year must not be in the acronym.")
        return v
