import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from xml.parsers.expat import model

import pandas as pd
from pydantic import BaseModel, model_validator
from typing_extensions import Self

from cvf.proceedings_stamper.config import ProceedingsConfig
from cvf.proceedings_stamper.paper import Paper, nearest_ascii, strip_latex_characters


class PaperList(BaseModel):
    papers: list[Paper]
    config: ProceedingsConfig

    @classmethod
    def read_paper_list(cls, config: ProceedingsConfig):
        """Parse the paper list from the spreadsheet specified in the config."""
        df = pd.read_csv(str(config.spreadsheet.url))

        paper_list = []
        columns = config.spreadsheet.columns
        # are all columns present?
        errors = []
        for config_key, column_name in columns.model_dump().items():
            if config_key != "authors_separator":
                if column_name not in df.columns:
                    errors.append(
                        f"Spreadsheet is missing a column mentioned in the config file:\n    {config_key} = {column_name!r}"
                    )
        if errors:
            errors.append(
                f"The spreadsheet has one of the following unaccounted columns: {set(df.columns) - set(columns.model_dump().values())}"
            )
            raise ValueError("\n".join(errors))
        for row_idx, row in df.iterrows():
            row = row.fillna(None).to_dict()

            if row[columns.title] and row[columns.input_filename]:
                filename = row[columns.input_filename]
                if "\\" in filename:
                    filename = filename.split("\\")[-1]
                paper = Paper(
                    conference_acronym=config.acronym,
                    title=row[columns.title],
                    abstract=row[columns.abstract],
                    authors=[
                        a.strip()
                        for a in row[columns.authors].split(columns.authors_separator)
                    ],
                    conference_long=config.long_name,
                    year=config.year,
                    start_page=int(row[columns.first_page])
                    if columns.first_page
                    else None,
                    last_page=int(row[columns.last_page])
                    if columns.last_page
                    else None,
                    supplemental_filename=row[columns.supplemental_filename],
                    # output_filename_prefix=row[columns.output_filename_prefix],
                    page_number_locations=(
                        None
                        # json.loads(row[COL_PAGE_NUMBER_LOCATIONS])
                        # if row[COL_PAGE_NUMBER_LOCATIONS]
                        # else None
                    ),
                    input_path=config.input_path / row[columns.input_filename],
                    output_directory=config.output_path,
                )
                paper_list.append(paper)

        return cls(papers=paper_list, config=config)

    @model_validator(mode="after")
    def validate_papers(self) -> Self:
        paper_list = self.papers
        input_pdfs = set(self.config.input_path.glob("*.pdf"))
        if len(input_pdfs) == 0:
            raise ValueError(
                f"No PDF files found in input directory {self.config.input_path}"
            )

        # Are output filenames unique?
        if len(set([paper.sensible_output_basename for paper in paper_list])) != len(
            paper_list
        ):
            counter = Counter([paper.sensible_output_basename for paper in paper_list])
            duplicate_papers = [
                str(paper)
                for paper in paper_list
                if counter[paper.sensible_output_basename] > 1
            ]
            raise ValueError(
                f"Papers don't have unique output filenames!\nA list of duplicates: {'\n\n'.join(duplicate_papers)}"
            )

        # Are input filenames unique?
        assert len(set([paper.input_path for paper in paper_list])) == len(
            paper_list
        ), (
            "Papers don't have unique input filenames! Ensure there are no duplicate paper IDs"
        )
        # Do all papers have input files? Are there any input files that don't have papers?
        missing_papers = [
            paper for paper in paper_list if not paper.input_path.exists()
        ]
        assert not missing_papers, (
            "The following papers are missing their input file:\n%s"
            % "\n\n".join(map(str, missing_papers))
        )

        # Are all PDFs accounted for?
        unaccounted_input_pdfs = input_pdfs - set([p.input_path for p in paper_list])
        assert not unaccounted_input_pdfs, (
            "The following PDF files do not have papers:\n\n"
            + "\n".join(map(str, unaccounted_input_pdfs))
        )
        return self
