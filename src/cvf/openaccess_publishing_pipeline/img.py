from calendar import c
from functools import partial
from itertools import accumulate
from typing import Literal

from matplotlib.pylab import isin
from PIL import Image

BG_COLOR = (224, 224, 224)


def beside(
    images,
    margin=2,
    border=2,
    color=BG_COLOR,
    direction: Literal["horizontal", "vertical"] = "horizontal",
):
    """Concatenate images with a margin of 'margin' pixels between them, and a background color of 'color'."""
    images = list(images)
    if not images:
        raise ValueError("beside() requires at least one image")

    axis = 0 if direction == "horizontal" else 1
    cross_axis = 1 - axis
    sizes = [image.size for image in images]
    offsets = [0, *accumulate(size[axis] + margin for size in sizes[:-1])]
    offsets = [offset + border for offset in offsets]

    output_size = [0, 0]
    output_size[axis] = offsets[-1] + sizes[-1][axis] + border
    output_size[cross_axis] = max(size[cross_axis] for size in sizes) + 2 * border

    out = Image.new("RGB", tuple(output_size), color=color)
    for image, offset in zip(images, offsets):
        position = [border, border]
        position[axis] = offset
        out.paste(image, tuple(position))
    return out


def crop(
    image: Image.Image | list[Image.Image],
    anchor: Literal["top_center", "bottom_center"],
    *,
    width_inches: float | None = None,
    height_inches: float | None = None,
    dpi: int = 72,
):
    """Crops an image (or a list of images) to the specified width and height in inches, anchored at the specified position."""
    if isinstance(image, Image.Image):
        image = [image]
        is_one_image = True
    else:
        is_one_image = False

    results = []
    for img in image:
        if width_inches is None:
            width = img.width
        else:
            width = int(width_inches * dpi)
        if height_inches is None:
            height = img.height
        else:
            height = int(height_inches * dpi)

        if anchor == "top_center":
            left = max(0, (img.width - width) // 2)
            upper = 0
        elif anchor == "bottom_center":
            left = max(0, (img.width - width) // 2)
            upper = max(0, img.height - height)
        else:
            raise ValueError(f"Invalid anchor: {anchor}")

        cropped = img.crop((left, upper, left + width, upper + height))
        results.append(cropped)
    if is_one_image:
        return results[0]
    return results


hcat = partial(beside, direction="horizontal")
vcat = partial(beside, direction="vertical")
