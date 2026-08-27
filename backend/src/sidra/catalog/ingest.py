from __future__ import annotations

from collections.abc import Iterable, Sequence

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.corpus_spec import CorpusSpec
from sidra.catalog.resolve import unit_count
from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.shape import ShapeNode, parse_shape
from sidra.catalog.work_draft import WorkDraft

_TRAILING_TRIM_SCHEMES = frozenset({AddressScheme.FLAT, AddressScheme.NESTED})


def _trim_trailing_empties(scheme: AddressScheme, chapters: Sequence[int]) -> tuple[int, ...]:
    """Drop trailing zero-length entries, and only trailing ones.

    Sefaria reports Orchot Tzadikim as 29 gates with the 29th empty, and Mesillat Yesharim as 27
    perakim with the 27th empty. One rule fixes both.

    Interior empties are never dropped: a ``FLAT`` entry's position is its identity, and Nazir's
    index-65 gap is meaningful positional data that ``real_amudim`` already handles for
    ``DAF_AMUD``. Compacting a shape would silently renumber every unit after the gap.
    """
    trimmed = list(chapters)
    if scheme in _TRAILING_TRIM_SCHEMES:
        while trimmed and trimmed[-1] == 0:
            trimmed.pop()
    return tuple(trimmed)


def _expand(node: ShapeNode, expand_complex: bool) -> list[ShapeNode]:
    """A complex node's ``chapters`` are child lengths, not unit counts.

    Shulchan Arukh, Even HaEzer is 178 simanim plus Seder HaGet and Seder Halitzah. Treating its
    three-element ``chapters`` as a flat work would give it three units instead of 178, so its
    children become works in their own right.
    """
    if expand_complex and node.is_complex and node.children:
        return list(node.children)
    return [node]


def _selected(nodes: Iterable[ShapeNode], spec: CorpusSpec) -> list[ShapeNode]:
    kept: list[ShapeNode] = []
    for node in nodes:
        if spec.include_section_prefix is not None and not node.section.startswith(spec.include_section_prefix):
            continue
        if node.section in spec.exclude_sections:
            continue
        if node.title is None or node.title in spec.exclude_titles:
            continue
        # Excluded again after expanding: a complex node's children carry their own titles, and
        # Even HaEzer's two appendices only exist once it has been split.
        kept.extend(
            child
            for child in _expand(node, spec.expand_complex)
            if child.title is not None and child.title not in spec.exclude_titles
        )
    return kept


def _ordered(nodes: Sequence[ShapeNode], spec: CorpusSpec) -> list[ShapeNode]:
    """Apply an explicit order when the corpus has one Sefaria does not share.

    Ketuvim is the case: Sefaria places Koheles last, after Divrei HaYamim, where the traditional
    printed order puts it among the Megillos.
    """
    if spec.order_override is None:
        return list(nodes)

    by_title = {node.title: node for node in nodes}
    missing = [title for title in spec.order_override if title not in by_title]
    if missing:
        raise ValueError(f"{spec.corpus_id}: order override names works absent from the shape: {missing}")
    unlisted = [node.title for node in nodes if node.title not in set(spec.order_override)]
    if unlisted:
        raise ValueError(f"{spec.corpus_id}: shape holds works the order override omits: {unlisted}")
    return [by_title[title] for title in spec.order_override]


def build_drafts(nodes: Sequence[ShapeNode], spec: CorpusSpec) -> list[WorkDraft]:
    """Turn parsed shape nodes into work drafts. Pure -- no network, no session."""
    drafts: list[WorkDraft] = []
    for corpus_seq, node in enumerate(_ordered(_selected(nodes, spec), spec), start=1):
        shape = _trim_trailing_empties(spec.address_scheme, node.chapters)
        assert node.title is not None  # noqa: S101 - _selected drops title-less nodes
        drafts.append(
            WorkDraft(
                corpus_id=spec.corpus_id,
                corpus_seq=corpus_seq,
                index_title=node.title,
                ref_title=node.title,
                title_he=node.title_he,
                granularity=spec.granularity,
                address_scheme=spec.address_scheme,
                shape=shape,
                labels=None,
                unit_count=unit_count(spec.address_scheme, shape),
                source="sefaria",
            )
        )
    return drafts


async def ingest_corpus(client: SefariaClient, spec: CorpusSpec) -> list[WorkDraft]:
    """Fetch one corpus's shape and build a draft per work."""
    return build_drafts(parse_shape(await client.shape(spec.shape_path)), spec)
