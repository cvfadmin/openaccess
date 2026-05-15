import io

import numpy as np
import pikepdf
from reportlab.pdfgen import canvas
from skimage import morphology

from cvf.proceedings_stamper.pdf_io import pdf_to_rgba


def create_pagenumber_stamp(page, out_page_number, page_stamp_location):
    """Returns a PikePDF "Page" instance that shows the stamp with
    'out_page_number'. The stamp is placed at x=center of the page,
    y=page_stamp_location points from the bottom.

    Arguments:
        page: a PikePDF page. Only the mediabox is used.
        out_page_number: An integer to print.
        page_stamp_location: How many points from the bottom of the page to show the page number.
    """
    content = io.BytesIO()
    pagewidth = float(page.mediabox[2])
    pageheight = float(page.mediabox[3])
    c = canvas.Canvas(content, pagesize=(8.5 * 72, 11 * 72), pdfVersion=(1, 4))
    c.setFillColorRGB(1, 1, 1)
    pagewidth = float(page.mediabox[2])
    rectw, recth = 72, 14
    c.rect(
        x=(pagewidth / 2.0 - rectw / 2.0),
        y=page_stamp_location - 3,
        width=rectw,
        height=recth,
        fill=True,
        stroke=False,
    )
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.setFont("Times-Roman", 9)
    c.drawCentredString(
        x=pagewidth / 2.0,
        y=page_stamp_location,
        text="%d" % out_page_number,
    )
    c.showPage()
    c.save()
    content.seek(0)
    return pikepdf.Pdf.open(content)


def guess_page_number_locations(pdf_filename, debug=False):
    """Problem: Authors have creative interpretations of
    the submission instructions. Some PDF
    files are fearfully and wonderfully made, and may suffer from any
    combination of the following:

    - Incorrect page numbers, numbered from page 1
    - The above, but only on the first page
    - The above, but on all pages except the first page
    - Generating a US Letter-sized paper and then cropping it in the
      middle of an A4 page (this means we can't hardcode the stamp
      location)
    - Simply submitting an A4-sized paper which violates
      submission guidelines
    - Creating figures that bleed into the page margins, which would
      show up underneath the stamped page number
    - Turning the entire PDF file into a sequence of concatenated
      bitmaps, making textual detection of page numbers completely
      impossible
    - Permuting all of the letters in the OCR layer to foil
      copy+pasting, making text detection of page numbers impossible

    To get around these issues, we need to guess where the page number
    is using some basic hand-tuned image processing: we crop off a
    region near the lower center of the paper and use filters to
    detect whether there's a page-number-sized area of text below the
    body copy.

    """
    results = []
    prev_location = None
    assert pdf_filename is not None
    pdf = pikepdf.Pdf.open(pdf_filename)
    n_pages = len(pdf.pages)
    for page_num, img in enumerate(pdf_to_rgba(pdf_filename, dpi=72)):
        img = img.mean(2)

        # Erode the image, to smooth over text regions.
        img = morphology.erosion(
            img,
            np.ones((18, 18)),
        )

        # Row_avgs is a measure of how likely each row contains a page
        # number. This is calculated as follows: things in the MIDDLE
        # should count TOWARD the pagenumber score; things near the
        # OUTSIDE should count AGAINST. The final result is a 1-d
        # array with length equal to the document's height in points.
        xmidpoint = int(img.shape[1] / 2.0)
        xleft = xmidpoint - 25
        xright = xmidpoint + 10
        # import IPython; IPython.embed()
        row_avgs = (
            (255 - img[:, xleft:xright]).sum(1)
            - (255 - img[:, :xleft]).sum(1)
            - (255 - img[:, xright:]).sum(1)
        )
        row_avgs = row_avgs[::-1]

        # # Next, smooth this value again
        # row_avgs_smoothed = (np.convolve(row_avgs, np.ones(12)/12., mode='same'))

        if debug:
            from matplotlib.pylab import subplots

            fig, (ax1, ax2) = subplots(1, 2, figsize=(8, 4))
            ax1.plot(row_avgs)
            ax1.set_xlim(0, 200)
            # The 256--356 is a vertical section that's slightly more than
            # an inch.
            img[:, xleft:xright] *= 0.8
            ax2.imshow(img[500:], cmap="gray")

        # Second step: Find if there's a page number at the bottom.
        # This will be indicated by a positive value for the score.
        proposed_page_number_location = None
        if np.any(row_avgs > 1000):
            proposed_locs = np.where(row_avgs > 0)[0]
            if np.all(row_avgs[: proposed_locs[0] + 12] >= 0):
                # The page number should be WELL below the rest of the body
                # text.
                proposed_page_number_location = proposed_locs[0] + 7

        if debug:
            print("Proposing", proposed_page_number_location)

        # Use this location, maybe.
        if proposed_page_number_location and page_num != n_pages - 1:
            # why is that last term necessary? ^^^^^^^^^^^^^^^^
            # Use this location
            results.append(proposed_page_number_location)
            prev_location = proposed_page_number_location
        else:
            # No page numbers here, OR they're likely to overlap with
            # some badly-behaved figures... hmm...
            first_ink_location = np.where(row_avgs < 0)[0][0]
            if debug:
                print("First ink location:", first_ink_location)
            if not prev_location or prev_location + 12 > first_ink_location:
                # uh oh, have to guess! just.... put it...halfwayish?
                prev_location = int(first_ink_location / 2.0)
            results.append(prev_location)

    return results
