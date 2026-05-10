import cairosvg
import pymupdf
import pikepdf
import unidecode
import re

def pdf_to_png_buffers(pdf, dpi=72):
  if isinstance(pdf, io.BytesIO):
    doc = pymupdf.open("pdf", pdf)
  else:
    doc = pymupdf.open(pdf)
  for page in doc:
    yield Image.open(io.BytesIO(page.get_pixmap(dpi=dpi).tobytes()))

def pdf_to_rgba(filename):
  for png_buffer in pdf_to_png_buffers(filename):
  #for page in fitz.open(filename):
  #  img = page.get_pixmap(dpi=72)
  #  img = np.array(img)
    img = imread(io.BytesIO(png_buffer))
    if img.ndim == 2:
        img = img[:,:, np.newaxis][:,:,[0,0,0]]
    yield img

def nice_open_pdf_file(filename):
    """ Run QPDF and then Ghostscript on the PDF file """
    assert os.path.exists(filename), "%s does not exist"%filename

    return pikepdf.Pdf.open(filename) # let's try bypassing ghostscript

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

def nearest_ascii(ustring):
    """ Given an encoded string that may contain UTF-8 or Latin-1 high
    bytes, try to convert it completely ASCII. This is suitable for
    filenames and author lists. """
    if not isinstance(ustring,str):
        try:
            ustring = ustring.decode('utf-8')
        except:
            try:
                ustring = ustring.decode("iso-8859-1")
            except:
                raise ValueError(ustring)
    # return unicodedata.normalize('NFKD', ustring).encode('ascii','ignore')
    return unidecode.unidecode(ustring)

def sanitize_for_filename(string):
    return re.compile(r"[^-a-zA-Z_.0-9]").subn("",nearest_ascii(string))[0]