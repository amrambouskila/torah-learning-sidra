"""Ingest works whose unit names cannot be derived from a count.

Orchot Tzadikim is the case in this sidra: its shape gives 28 gates but not their names, which live
in the index alt-struct. The names ride on the ``Work`` as ``labels`` / ``labels_he``, so the work
stays a derived ``FLAT`` work rather than becoming 28 stored rows.
"""

from __future__ import annotations

from dataclasses import dataclass

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.corpus_spec import CorpusSpec
from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest import build_drafts
from sidra.catalog.sefaria_client import SefariaClient
from sidra.catalog.shape import parse_shape
from sidra.catalog.work_draft import WorkDraft


@dataclass(frozen=True, slots=True)
class NamedWorkSpec:
    """A work whose units are counted by the shape but named by an alt-struct."""

    corpus_id: str
    corpus_seq: int
    ref_title: str
    alt_key: str
    granularity: Granularity


def alt_struct_labels(index_payload: dict[str, object], alt_key: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Read English and Hebrew unit names from ``alts.<alt_key>.nodes``.

    Titles are stripped: Orchot Tzadikim's gates 11 and 28 carry a trailing newline in their Hebrew
    titles, which would otherwise propagate into every label built from them.
    """
    alts = index_payload.get("alts")
    if not isinstance(alts, dict) or alt_key not in alts:
        raise ValueError(f"index payload carries no alts.{alt_key} structure")

    nodes = alts[alt_key].get("nodes", [])
    english = tuple(str(node.get("title", "")).strip() for node in nodes)
    hebrew = tuple(str(node.get("heTitle", "")).strip() for node in nodes)
    if not english:
        raise ValueError(f"alts.{alt_key} holds no nodes")
    return english, hebrew


def attach_labels(draft: WorkDraft, english: tuple[str, ...], hebrew: tuple[str, ...]) -> WorkDraft:
    """Attach unit names to a draft, refusing a length that does not match the unit count.

    A mismatch would otherwise produce an off-by-one on every later lookup rather than an error.
    """
    for name, labels in (("labels", english), ("labels_he", hebrew)):
        if len(labels) != draft.unit_count:
            raise ValueError(
                f"{draft.ref_title}: {name} has {len(labels)} entries but the work holds {draft.unit_count} units"
            )
    return WorkDraft(
        corpus_id=draft.corpus_id,
        corpus_seq=draft.corpus_seq,
        index_title=draft.index_title,
        ref_title=draft.ref_title,
        title_he=draft.title_he,
        granularity=draft.granularity,
        address_scheme=draft.address_scheme,
        shape=draft.shape,
        labels=english,
        unit_count=draft.unit_count,
        source=draft.source,
        labels_he=hebrew,
    )


async def ingest_named_work(client: SefariaClient, spec: NamedWorkSpec) -> WorkDraft:
    """Fetch a work's shape and its alt-struct names, and marry them."""
    nodes = parse_shape(await client.shape(spec.ref_title))
    drafts = build_drafts(
        nodes,
        CorpusSpec(
            corpus_id=spec.corpus_id,
            shape_path=spec.ref_title,
            granularity=spec.granularity,
            address_scheme=AddressScheme.FLAT,
        ),
    )
    if not drafts:
        raise ValueError(f"{spec.ref_title}: shape produced no work")
    draft = drafts[0]
    english, hebrew = alt_struct_labels(await client.index(spec.ref_title), spec.alt_key)
    return attach_labels(
        WorkDraft(
            corpus_id=spec.corpus_id,
            corpus_seq=spec.corpus_seq,
            index_title=draft.index_title,
            ref_title=draft.ref_title,
            title_he=draft.title_he,
            granularity=spec.granularity,
            address_scheme=draft.address_scheme,
            shape=draft.shape,
            labels=None,
            unit_count=draft.unit_count,
            source=draft.source,
        ),
        english,
        hebrew,
    )
