from collections.abc import Iterator, Sequence

from lark import Lark, Transformer
from lark.exceptions import LarkError
from skimage.feature.orb import i

from cvf.openaccess_publishing_pipeline.paper import Paper
from cvf.openaccess_publishing_pipeline.paper_list import PaperList

pickaxe_range_parser = Lark(r"""

start : range ("," range)*

?range : NUMBER -> single
      | dashedrange
      | colonslice

dashedrange : dashedstart? "-" dashedstop?
dashedstart: NUMBER
dashedstop: NUMBER

colonslice     : slicestart? ":" sliceend? (":" slicestep)?
slicestart: NUMBER
sliceend:   NUMBER
slicestep:  NUMBER

%import common.NUMBER

""")


class PickaxeRangeTransformer(Transformer):
    def single(self, items):
        n = int(items[0])
        return slice(n, n + 1)

    def dashedrange(self, items):
        if len(items) == 0:
            return slice(None)
        elif len(items) == 1:
            if items[0].data == "dashedstart":
                start = int(items[0].children[0])
                return slice(start, None)
            else:
                stop = int(items[0].children[0])
                return slice(None, stop + 1)
        elif len(items) == 2:
            start = int(items[0].children[0])
            stop = int(items[1].children[0])
            return slice(start, stop + 1)

    def colonslice(self, items):
        start = None
        stop = None
        step = None
        for item in items:
            if item.data == "slicestart":
                start = int(item.children[0])
            elif item.data == "sliceend":
                stop = int(item.children[0])
            elif item.data == "slicestep":
                step = int(item.children[0])
        return slice(start, stop, step)

    start = list


def apply_search_terms(
    paper_list: Sequence[Paper], search_terms: str | None
) -> Iterator[Paper]:
    if not search_terms:
        yield from paper_list
        return
    count = 0

    try:
        tree = pickaxe_range_parser.parse(search_terms)
        slices = PickaxeRangeTransformer().transform(tree)
        for s in slices:
            count += len(paper_list[s])
            yield from paper_list[s]
    except LarkError as exc:
        # Try to parse as an author name, filename, or title
        for paper in paper_list:
            if (
                search_terms.lower() in " ".join(paper.authors).lower()
                or search_terms.lower() in str(paper.input_path).lower()
                or search_terms.lower() in str(paper.output_path).lower()
                or search_terms.lower() in paper.title.lower()
            ):
                count += 1
                yield paper
    if count == 0:
        print(f'No papers found matching search terms "{search_terms}".')
