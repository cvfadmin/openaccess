from pathlib import Path

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator
from pydantic.types import DirectoryPath


class PaperListSpreadsheetColumnsConfig(BaseModel):
    "List of column names in the spreadsheet. These are used to extract the title and abstract of each paper, which are then used to generate the banner text."

    model_config = ConfigDict(use_attribute_docstrings=True, extra="forbid")

    title: str
    "Column of the paper title."

    abstract: str
    "Column of the paper abstract."

    authors: str
    "Column of the paper authors."

    authors_separator: str
    "The string that separates the authors in the authors column. Usually ';' or ',' depending on the IEEE spreadsheet."

    input_filename: str
    "Column of the input PDF filename. This should match the filename of the PDF in the input directory."

    supplemental_filename: str
    "Column of the supplemental material filename. This should match the filename of the supplemental material in the input directory. This column can be empty if there is no supplemental material."

    first_page: str | None
    "Column of the first page number of the paper in the proceedings output."

    last_page: str | None
    "Column of the last page number of the paper in the proceedings output. Paper PDFs must be (last_page - first_page + 1) pages long."


class PaperListSpreadsheetConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True, extra="forbid")

    url: AnyUrl
    """URL to the spreadsheet in CSV format. For Google sheets, you can use the URL, see https://stackoverflow.com/questions/33713084/download-link-for-google-spreadsheets-csv-export-with-multiple-sheets"""

    columns: PaperListSpreadsheetColumnsConfig


class BannerConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True, extra="forbid")

    text: tuple[str, ...]
    """Banner contents to be stamped at the top of the first page."""

    @field_validator("text", mode="before")
    def validate_text(cls, v: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
        raw_lines = v.strip().splitlines() if isinstance(v, str) else v
        txt = tuple(line.strip() for line in raw_lines if line.strip())
        if not txt:
            raise ValueError("Banner text must contain at least one non-empty line.")
        return txt


class ProceedingsConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True, extra="forbid")

    acronym: str
    """Four-letter acronym for the conference."""

    year: int = Field(ge=1900, le=2500)
    """Year of the conference."""

    long_name: str
    """Full conference name. 'IEEE Conference on Computer Vision and Pattern Recognition' for example."""

    input_path: DirectoryPath
    """Path to the directory containing PDF."""

    output_path: Path
    """Path to output files."""

    csv_output_path: Path = Path("papers.csv")
    """Path to the output CSV file relative to output_path."""

    zip_output_path: Path
    """Path to the output zip file."""

    report_output_path: Path
    """Path to the output HTML report for QA checks."""

    spreadsheet: PaperListSpreadsheetConfig

    banner: BannerConfig

    @field_validator("acronym")
    def validate_acronym(cls, v: str) -> str:
        if not v.isupper():
            raise ValueError("Acronym must be uppercase, i.e.  'CVPR'")
        if not v.isalpha():
            raise ValueError("Year must not be in the acronym.")
        return v

    @field_validator("long_name")
    def validate_long_name(cls, v: str) -> str:
        if any(char.isdigit() for char in v):
            raise ValueError("Year must not be in the long name.")
        return v
