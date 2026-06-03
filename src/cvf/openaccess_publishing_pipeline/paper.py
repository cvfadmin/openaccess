import csv
import re
import tempfile
from pathlib import Path
from typing import Any, Literal

import unidecode
from nameparser import HumanName
from pydantic import BaseModel, ConfigDict, computed_field

from cvf.openaccess_publishing_pipeline import stamp_firstpage_banner, stamp_pagenumber
from cvf.openaccess_publishing_pipeline.config import ProceedingsConfig
from cvf.openaccess_publishing_pipeline.img import beside
from cvf.openaccess_publishing_pipeline.pdf_io import nice_open_pdf_file, pdf_to_rgb


class Paper(BaseModel):
    """A record of one single paper in the proceedings."""

    index: int
    "0-indexed paper number (by row order in the spreadsheet)."

    model_config = ConfigDict(
        use_attribute_docstrings=True, extra="forbid", arbitrary_types_allowed=True
    )

    input_path: Path
    """Absolute path to the input PDF file."""

    title: str
    """Paper title. May contain LaTeX characters."""

    authors: list[str]
    """List of author names. Each author has the format "Firstname Lastname"."""

    abstract: str
    """Long abstract. May contain LaTeX characters."""

    conference_acronym: str
    """Short conference acronym, like "WACV"."""

    year: int
    """Full year, like "2024"."""

    conference_long: str
    """Full conference title. "Winter conference on Applications of Computer Vision"."""

    start_page: int | None
    """First page number."""

    last_page: int | None
    """Last page number."""

    supplemental_filename: str | None
    """Basename of the supplemental material file, if it exists."""

    output_filename_prefix: str | None = None
    """Per-paper output path prefix (may include subdirectory). E.g. 'workshop_5/5-' places the paper at output_directory/workshop_5/5-<basename>."""

    pagenumber_tile: Any = None
    page_tile: Any = None

    page_number_locations: list[float] | None
    """Array of stamp offset values for each page.

    Offsets are in units of 1/72 of an inch, counting from the bottom of the
    page upwards. The length of this array should be the number of pages of the input.

    Context: Authors frequently forget to turn off page numbering in their
    camera-ready files. We often receive papers that have incorrect page
    numbers at the bottom of each page. To correct for this, we stamp white
    rectangles to cover the incorrect page numbers, and then stamp our own.
    This array allows us to override the automatic page number detection
    heuristic with offsets of our choosing.
    """

    output_directory: Path
    """Absolute path to the paper output folder."""

    @computed_field
    @property
    def output_path(self) -> Path:
        basename = self.sensible_output_basename
        if self.output_filename_prefix:
            return self.output_directory / (self.output_filename_prefix + basename)
        return self.output_directory / basename

    def __str__(self):
        return "\n".join(
            [
                # (f"[row {self._row_idx}]\n" if self._row_idx is not None else ""),
                "\x1b[0;30m" + str(self.input_path) + "\x1b[0m",
                "\x1b[1;32m" + self.title + "\x1b[0m",  # + ", p.%d"%self.start_page
                ", ".join(self.authors),
            ]
        )

    def stamp(
        self,
        config: ProceedingsConfig,
        *,
        stamp_page_numbers=True,
        verify_page_counts=True,
    ):
        """Perform the following actions on paper:
        - Read it from the input folder
        - Give it proper metadata
        - Give it the CVF banner
        - Give it proper page numbers
        - Give it a proper filename
        - Copy it to the output folder
        """

        pdf_in = nice_open_pdf_file(self.input_path)
        pdf_out = pdf_in
        # note that we are editing pdf_in in-place, though saving it to a new
        # file. changes not saved until the file is written. If we created a new
        # pikepdf object for output, we would have to go through extra effort to
        # preserve hyperlinks and annotations!

        # Apply metadata
        if "/Metadata" in pdf_out.Root:
            del pdf_out.Root.Metadata
        del pdf_out.docinfo
        with pdf_out.open_metadata() as meta:
            meta["dc:title"] = nearest_ascii(self.title)
            meta["dc:creator"] = list(map(nearest_ascii, self.authors))
            meta["dc:description"] = self.conference_long

        self.output_path.parent.mkdir(exist_ok=True, parents=True)

        # Verify page count
        if self.last_page is not None and self.start_page is not None:
            n_pages = self.last_page - self.start_page + 1
            if len(pdf_in.pages) != n_pages:
                if verify_page_counts:
                    raise ValueError(
                        f"Problem with {self}:\nPDF file has {len(pdf_in.pages)}, but {n_pages} in the spreadsheet! Refusing to process this paper. Future papers almost certainly have incorrect page counts."
                    )
                else:
                    print(
                        f"Problem with {self}:\nPDF file has {len(pdf_in.pages)}, but {n_pages} in the spreadsheet! Continue at your peril. Future papers almost certainly have incorrect page counts."
                    )

        # Guess page number locations.
        # LaTeX default is to apply page numbers (1, 2, 3, ...) to each page.
        # Some authors forget to turn off page numbering.
        if stamp_page_numbers and self.start_page is not None:
            if self.page_number_locations:
                page_number_locations = self.page_number_locations
                page_number_locations = page_number_locations + [
                    page_number_locations[-1]
                ] * len(pdf_in.pages)
            else:
                page_number_locations = stamp_pagenumber.guess_page_number_locations(
                    self.input_path
                )
        else:
            page_number_locations = [None] * len(pdf_in.pages)

        # print(f"PDF debug: {self}\nFirst page:{self.start_page}\nLen(pdf_in.pages):{len(pdf_in.pages)}\npage_number_locations:{page_number_locations}")

        # Process each page
        for page_num, page_number_location in zip(
            range(len(pdf_in.pages)), page_number_locations
        ):
            page = pdf_in.pages[page_num]
            if page.mediabox != [0, 0, 612, 792]:
                # units in points (72 per inch)
                print(
                    "Problem: Page %d is NOT 8.5x11 size! Check to make sure it looks OK!"
                    % page_num
                )
                print("  Filename: %s" % self.input_path)

            # Sometimes ghostscript accidentally gets confused
            # and rotates our page... this flag doesn't affect any
            # of the drawing commands, but will ask the viewer
            # to rotate the page.
            if page.get("/Rotate", 0) != 0:
                page["/Rotate"] = 0

            # sometimes, the page may not reset the transformation matrix to
            # a known state. we get around this by wrapping the entire page in
            # a stack push/pop operation, which should reset everything.
            # see https://github.com/pikepdf/pikepdf/issues/259#issuecomment-933883802
            page.contents_add(b"q", prepend=True)
            page.contents_add(b"Q", prepend=False)
            page.contents_coalesce()

            # Strip author-added review markup (e.g. /Square comment boxes,
            # /Popup, /FreeText). These live outside the content stream, so the
            # q/Q wrap above can't suppress them, and they show up as draggable
            # objects in Preview. Use a denylist rather than an allowlist:
            # some papers embed video clips as /Screen and /Widget annotations
            # (LaTeX animate/media9 packages) whose appearance streams hold the
            # visible figure frames, so removing unknown subtypes would blank
            # out their figures. /Link survives so hyperref-generated
            # hyperlinks and cross-references do too.
            review_markup_subtypes = {
                "/Text",
                "/FreeText",
                "/Square",
                "/Circle",
                "/Polygon",
                "/PolyLine",
                "/Highlight",
                "/Underline",
                "/Squiggly",
                "/StrikeOut",
                "/Caret",
                "/Stamp",
                "/Ink",
                "/Popup",
                "/FileAttachment",
                "/Sound",
            }
            if "/Annots" in page:
                page["/Annots"] = [
                    a
                    for a in page["/Annots"]
                    if str(a.get("/Subtype", "")) not in review_markup_subtypes
                ]

            # Add the banner to the first page
            if page_num == 0:
                banner_pdf = stamp_firstpage_banner.make_banner_for_page(
                    page,
                    config.banner,
                )
                page.add_overlay(banner_pdf.pages[0], push_stack=True)

            # Add stamped page numbers to the output page
            if stamp_page_numbers and self.start_page is not None:
                out_page_number = page_num + self.start_page
                overlay = stamp_pagenumber.create_pagenumber_stamp(
                    page, out_page_number, page_number_location
                )
                page.add_overlay(overlay.pages[0], push_stack=True)
            # pdf_out.pages.append(page)
            # we are editing pdf_out (=pdf_in) in-place, so no
            # need to copy pages!
            # note that if we DID copy to a new document, we'd
            # need to go through additional steps to preserve
            # annotations and hyperlinks!

        # Finalize stamping the PDF
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=self.output_path.parent,
            prefix=f"{self.output_path.name}-tmp-",
            delete=False,
        ) as f:
            temp_path = Path(f.name)
            pdf_out.save(f, normalize_content=True)
        temp_path.replace(self.output_path)

    @computed_field
    @property
    def sensible_output_basename(self) -> str:
        """Generate a sensible final filename given a paper dictionary"""
        first_author = HumanName(self.authors[0])
        first_author.capitalize()
        name = (first_author.last or first_author.first).replace(" ", "_")
        first_few_words_of_title = "_".join(self.title.split(" ")[:10])
        return sanitize_for_filename(
            "%s_%s_%s_%d_paper.pdf"
            % (
                name,
                first_few_words_of_title,
                self.conference_acronym,
                self.year,
            )
        )

    @computed_field
    @property
    def sensible_supplemental_filename(self) -> str | None:
        """Generate a sensible final filename given a paper dictionary"""
        if not self.supplemental_filename:
            return None
        extension = self.supplemental_filename.split(".")[1]
        first_author = HumanName(self.authors[0])
        first_author.capitalize()
        name = (first_author.last or first_author.first).replace(" ", "_")
        first_three_words_of_title = "_".join(self.title.split(" ")[:3])
        return sanitize_for_filename(
            "%s_%s_%s_%d_supplemental.%s"
            % (
                name,
                first_three_words_of_title,
                self.conference_acronym,
                self.year,
                extension,
            )
        )

    def image(
        self,
        dpi=72,
        which: Literal["output", "input"] = "output",
        pages: Literal["first", "all"] = "all",
        format: Literal["numpy", "pil"] = "pil",
    ):
        if which == "input":
            path = self.input_path
        elif which == "output":
            path = self.output_path
        rendered = list(pdf_to_rgb(path, format=format, dpi=dpi, pages=pages))
        if pages == "first":
            return rendered[:1]
        else:
            return rendered


def strip_latex_characters(text):
    """
    Remove LaTeX characters from a string.
    """
    orig_text = text
    text = re.subn(r"\\inst{([1-9,]*)}?", r"", text)[0]
    text = re.subn(r"\\orcidID{([^}]*)}", r"", text)[0]
    text = re.subn(r"\\emph{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\textit{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\textbf{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\textsc{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\textcolor{[a-z]*}{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\mbox{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\mathbf{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\peng{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\footnote{([^}]*)}", r"(\1)", text)[0]
    text = re.subn(r"\\url{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\cite{([^}]*)}", r"[??]", text)[0]  #:)
    # the following rule deals with: "Ji{\v r}{\'{\i}} Hlad\r{u}vka"
    text = re.subn(r"{\\'{\\(.)}}", r"\1", text)[0]
    text = re.subn(r"{\\v\W*([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\'{\\(.)}", r"\1", text)[0]
    text = re.subn(r"\\'{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"{\\(.)}", r"\1", text)[0]
    text = re.subn(r"\\'{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\v{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\`{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\\"{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\~{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"{\\'\W*([^}]*)}", r"\1", text)[0]
    text = re.subn(r"{\\aa}", r"aa", text)[0]
    text = re.subn(r"{\\\"([^}]*)}", r"\1", text)[0]
    text = re.subn(r"{\\`([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\c{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\u{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\r{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\\^{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\`([^}]*)", r"\1", text)[0]
    text = re.subn(r"\\`{([^}]*)}", r"\1", text)[0]
    text = re.subn(r"\\'i", r"i", text)[0]
    text = re.subn(r"\\'e", r"e", text)[0]
    text = re.subn(r"\\'(.)", r"\1", text)[0]
    text = re.subn(r"\\frac{([^}]*)}{([^}]*)}", r"\1 / \2", text)[0]
    text = (
        text.replace("~", " ")
        .replace("$", "")
        .replace(r"\%", "%")
        .replace(r"\_", "_")
        .replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"``", '"')
        .replace(r"''", '"')
        .replace(r"\"", "")  # dropping \"o -> o
        .replace(r"\it ", "")
        .replace(r"\times ", "x")
        .replace(r"\times", "x")
        .replace(r"\beta", "b")
        .replace(r"\rightarrow", "->")
        .replace(r"\ ", " ")
        .replace(r"\eg", "e.g.")
        .replace(r"\chi", "Chi")
        .replace(r"\sim", "~")
        .replace(r"\approx", "~")
        .replace(r"\em", "")
        .replace(r"\bm", "")
        .replace(r"\infty", "infinity")
        .replace(r"\Phi", "Phi")
        .replace(r"\ell", "l")
        .replace(r"\epsilon", "epsilon")
        .replace(r"\it ", "it ")
        .replace(r"\textbf ", "")
        .replace(r"\bf ", "")
        .replace(r"\ryn ", "")  # wtf is this
        .replace(r"\ie ", "i.e. ")
        .replace(r"\ie", "i.e.")
        .replace(r"\etc", "etc.")
        .replace(r"\&", "&")
        .replace(r"\ll", "<<")
        .replace(r"\newline", "")
    )
    if "{" in text:
        print(
            "Warning: Stripping brackets:",
            text[text.index("{") - 30 : text.index("{") + 30],
        )
    text = text.replace("{", " ")
    if "}" in text:
        print(
            "Warning: Stripping brackets:",
            text[text.index("}") - 30 : text.index("}") + 30],
            repr(orig_text),
        )
    text = text.replace("}", " ")
    if "\\" in text:
        print(
            "Warning: Another \\-command:",
            text[text.index("\\") - 30 : text.index("\\") + 30],
            repr(orig_text),
        )
    return text


def nearest_ascii(ustring):
    """Given an encoded string that may contain UTF-8 or Latin-1 high
    bytes, try to convert it completely ASCII. This is suitable for
    filenames and author lists."""
    if not isinstance(ustring, str):
        try:
            ustring = ustring.decode("utf-8")
        except Exception:
            try:
                ustring = ustring.decode("iso-8859-1")
            except Exception:
                raise ValueError(ustring)
    # return unicodedata.normalize('NFKD', ustring).encode('ascii','ignore')
    return unidecode.unidecode(ustring)


def sanitize_for_filename(string):
    return re.compile(r"[^-a-zA-Z_.0-9]").subn("", nearest_ascii(string))[0]


def emit_csv(
    papers: list[Paper],
    config: ProceedingsConfig,
):
    """Convert all papers to a CSV file that's suitable to import into
    phpmyadmin"""
    with open(config.output_path / config.csv_output_path, "w") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_NONE, escapechar="\\")
        for paper in papers:
            pathname = (
                f"content_{config.acronym}_{config.year}/papers/"
                + (paper.output_filename_prefix or "")
                + paper.sensible_output_basename
            )
            supplemental_pathname = "None"
            if paper.supplemental_filename:
                supplemental_pathname = (
                    f"content_{config.acronym}_{config.year}/supplemental/"
                    + paper.sensible_supplemental_filename
                )
            writer.writerow(
                [
                    # Title
                    nearest_ascii(paper.title),
                    # Authors
                    nearest_ascii(", ".join(paper.authors)),
                    # PDF (filename)
                    pathname,
                    # Supplemental material
                    supplemental_pathname,
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
                ]
            )
