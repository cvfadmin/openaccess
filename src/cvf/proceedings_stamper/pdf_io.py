import io
from pathlib import Path

import numpy as np
import pikepdf
import pymupdf


def pdf_to_png_buffers(pdf, dpi=72):
    if isinstance(pdf, io.BytesIO):
        doc = pymupdf.open("pdf", pdf)
    else:
        doc = pymupdf.open(pdf)
    for page in doc:
        yield page.get_pixmap(dpi=dpi).tobytes(output="png")


def pdf_to_rgba(filename, dpi=72):
    if isinstance(filename, io.BytesIO):
        doc = pymupdf.open("pdf", filename)
    else:
        doc = pymupdf.open(filename)
    for page in doc:
        pixmap = page.get_pixmap(dpi=dpi, colorspace="rgb", alpha=False)
        arr = np.array(pixmap.pil_image())
        yield arr


def nice_open_pdf_file(filename: Path):
    assert filename.exists(), f"{filename} does not exist"
    return pikepdf.Pdf.open(filename)

    # PikePDF removes the need for below:
    """
    # Pass input thru qpdf to fix xref table
    #proc = subprocess.Popen(["qpdf", filename, "--replace-input"],
    #                        stdin=subprocess.PIPE,
    #                        stdout=subprocess.PIPE)
    #(out2, err) = proc.communicate("")
    #print "qpdf run: %r" % [out2, err]

    proc = subprocess.Popen([
            "gs",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            # see http://superuser.com/questions/360216/use-ghostscript-but-tell-it-to-not-reprocess-images
            #"-dJPEGQ=95", # default is 75

        # don't do this -- this sets the DPI to be horrible
            #"-dPDFSETTINGS=/printer",
            # "-dColorConversionStrategy=/LeaveColorUnchanged",
        # i don't think ghostscript downsamples images by default
            # "-dDownsampleMonoImages=false",
            # "-dDownsampleGrayImages=false",
            # "-dDownsampleColorImages=false",
        # turning these options balloons filesizes... a shame that ghostscript must reencode images by default
            # "-dAutoFilterColorImages=false",
            # "-dAutoFilterGrayImages=false",
            # "-dColorImageFilter=/DCTEncode",
            # "-dGrayImageFilter=/DCTEncode",
        # preserve hyperlinks
            "-dPreserveAnnots=true", "-dPrinted=false",
            "-sOutputFile=-",

            # better image quality when in screen mode
            # see https://stackoverflow.com/questions/40849325/ghostscript-pdfwrite-specify-jpeg-quality
            "-c",".setpdfwrite << /ColorACSImageDict << /VSamples [ 1 1 1 1 ] /HSamples [ 1 1 1 1 ] /QFactor 0.08 /Blend 1 >> /ColorImageDownsampleType /Bicubic /ColorConversionStrategy /LeaveColorUnchanged >> setdistillerparams",

            "-f", filename,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    (out,err) = proc.communicate("")

    return Pdf.open(io.BytesIO(out))
    """
