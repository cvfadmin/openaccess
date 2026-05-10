from dataclasses import dataclass
import pandas as pd
import paper

@dataclass
class PaperList:
    papers: list[paper.Paper]

class PaperListImporter:
    pass

@dataclass
class ExcelPaperListImporter(PaperListImporter):
    # Path to the paper list spreadsheet, relative to base_path.
    # May also be a URL to a google spreadsheet:
    # Instead of https://docs.google.com/spreadsheets/d/.../edit,
    # this can be https://docs.google.com/spreadsheets/d/.../export?format=xlsx
    # For this to work, the spreadsheet must be link-shared and publicly visible.
    spreadsheet_url_or_path: str

    # Column names in the Excel spreadsheet.
    col_title: str = "Title"
    col_abstract: str = "Abstract"
    col_authors: str = "Author"
    col_authors_sep: str = ","
    col_cameraready_filename: str = "Camera-Ready Filename"
    col_supplemental_filename: str = "Supplemental Filename"
    col_firstpage: str | None = "First Page"
    col_lastpage: str | None = "Last Page"

@dataclass
class ConferenceConfig:
    # Short conference acronym, like "WACV"
    conference_acronym: str

    # Full year, like "2024"
    year: str

    # Full conference title. "Winter conference on Applications of Computer Vision"
    conference_long: str

    # Path to this conference's folder. Defaults to the location of __main__.__file__
    base_path: Path

    # Path, relative to `base_path`, to PDF input folder.
    pdf_input_path: str
    # Path, relative to `base_path`, to the output folder.
    pdf_output_path: str
    # Zip file name, relative to `base_path`. Defaults to the basename of `pdf_output_path`.
    zip_output_path: str | None

    stamp_steps: list[Stamper]

    paperlist_importer: PaperListImporter



def emit_csv(papers,filename, pathname="content_cvpr_2015/papers/", supplemental_pathname="content_cvpr_2015/supplemental/"):
    """Convert all papers to a CSV file that's suitable to import into
       phpmyadmin"""
    with open(filename,"w") as f:
        writer = csv.writer(f,quoting=csv.QUOTE_NONE,escapechar="\\")
        for paper in papers:
            writer.writerow([
                # Title
                nearest_ascii(paper.title),
                # Authors
                nearest_ascii(", ".join(paper.authors)),
                # PDF (filename)
                pathname+paper.sensible_filename(),
                # Supplemental material
                (supplemental_pathname+paper.sensible_supplemental_filename()
                 if paper.supplemental_filename
                 else "None"),
                # Original filename
                (paper.supplemental_filename or "None"),
                # Slides
                "None",
                # Poster
                "None",
                # Xplore
                "None",
                # First page
                paper.start_page,
                # Last page
                paper.last_page,
                # Abstract
                strip_latex_characters(nearest_ascii(paper.abstract)),
                ])