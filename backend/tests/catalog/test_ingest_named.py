from __future__ import annotations

import pytest

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.granularity import Granularity
from sidra.catalog.ingest_named import alt_struct_labels, attach_labels
from sidra.catalog.resolve import unit_at
from sidra.catalog.work_draft import WorkDraft

# Orchot Tzadikim as the real index reports it: gates 11 and 28 carry a trailing newline.
ORCHOT_INDEX = {
    "alts": {
        "Gate": {
            "nodes": [
                {"title": "Chapter One: ON PRIDE", "heTitle": "שער הראשון - שער הגאווה"},
                {"title": "Chapter Two: ON HUMILITY", "heTitle": "שער השני - שער הענווה"},
                {"title": "Chapter Eleven: ON REMORSE", "heTitle": "שער האחד-עשר - שער החרטה\n"},
            ]
        }
    }
}

DRAFT = WorkDraft(
    corpus_id="mussar",
    corpus_seq=1,
    index_title="Orchot Tzadikim",
    ref_title="Orchot Tzadikim",
    title_he="אורחות צדיקים",
    granularity=Granularity.GATE,
    address_scheme=AddressScheme.FLAT,
    shape=(45, 44, 11),
    labels=None,
    unit_count=3,
    source="sefaria",
)


def test_labels_are_read_from_the_alt_struct() -> None:
    english, hebrew = alt_struct_labels(ORCHOT_INDEX, "Gate")
    assert english[0] == "Chapter One: ON PRIDE"
    assert hebrew[0] == "שער הראשון - שער הגאווה"


def test_the_trailing_newline_is_stripped() -> None:
    """A measured trap: gate 11's heTitle ends with a newline in the real payload."""
    _, hebrew = alt_struct_labels(ORCHOT_INDEX, "Gate")
    assert hebrew[2] == "שער האחד-עשר - שער החרטה"
    assert not hebrew[2].endswith("\n")


def test_a_missing_alt_struct_raises() -> None:
    with pytest.raises(ValueError, match="alts.Gate"):
        alt_struct_labels({"alts": {"Parasha": {}}}, "Gate")


def test_an_empty_alt_struct_raises() -> None:
    with pytest.raises(ValueError, match="no nodes"):
        alt_struct_labels({"alts": {"Gate": {"nodes": []}}}, "Gate")


def test_attaching_labels_sets_both_label_sets() -> None:
    english, hebrew = alt_struct_labels(ORCHOT_INDEX, "Gate")
    labelled = attach_labels(DRAFT, english, hebrew)
    assert labelled.labels == english
    assert labelled.labels_he == hebrew
    assert labelled.shape == DRAFT.shape


@pytest.mark.parametrize("field", ["labels", "labels_he"])
def test_a_label_length_mismatch_raises(field: str) -> None:
    """Otherwise it is an off-by-one on every later lookup instead of an error."""
    english, hebrew = alt_struct_labels(ORCHOT_INDEX, "Gate")
    short = ("only-one",)
    with pytest.raises(ValueError, match=field):
        attach_labels(DRAFT, short if field == "labels" else english, short if field == "labels_he" else hebrew)


def test_a_labelled_work_still_derives_its_units() -> None:
    """The names ride on the work; the units stay derived rather than becoming 28 rows."""
    english, hebrew = alt_struct_labels(ORCHOT_INDEX, "Gate")
    labelled = attach_labels(DRAFT, english, hebrew)
    unit = unit_at(
        labelled.ref_title,
        labelled.address_scheme,
        labelled.shape,
        3,
        labels=labelled.labels,
        labels_he=labelled.labels_he,
    )
    assert unit.label_en == "Chapter Eleven: ON REMORSE"
    assert unit.label_he == "שער האחד-עשר - שער החרטה"
    assert unit.ref == "Orchot Tzadikim 3"
    assert unit.child_count == 11


async def test_ingest_named_work_marries_the_shape_and_the_alt_struct() -> None:
    import httpx

    from sidra.catalog.ingest_named import NamedWorkSpec, ingest_named_work
    from sidra.catalog.sefaria_client import SefariaClient

    shape_payload = [
        {
            "title": "Orchot Tzadikim",
            "heTitle": "אורחות צדיקים",
            "section": "Musar",
            "length": 4,
            "chapters": [45, 44, 11, 0],
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        payload = shape_payload if "/shape/" in request.url.path else ORCHOT_INDEX
        return httpx.Response(200, json=payload)

    client = SefariaClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)), "https://www.sefaria.org/api")
    draft = await ingest_named_work(
        client,
        NamedWorkSpec(
            corpus_id="mussar",
            corpus_seq=1,
            ref_title="Orchot Tzadikim",
            alt_key="Gate",
            granularity=Granularity.GATE,
        ),
    )
    # The trailing empty gate is trimmed, leaving three that the alt-struct names.
    assert draft.unit_count == 3
    assert draft.labels is not None and len(draft.labels) == 3
    assert draft.labels_he is not None and not draft.labels_he[2].endswith("\n")


async def test_ingest_named_work_raises_when_the_shape_yields_nothing() -> None:
    import httpx

    from sidra.catalog.ingest_named import NamedWorkSpec, ingest_named_work
    from sidra.catalog.sefaria_client import SefariaClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[] if "/shape/" in request.url.path else ORCHOT_INDEX)

    client = SefariaClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)), "https://www.sefaria.org/api")
    with pytest.raises(ValueError, match="produced no work"):
        await ingest_named_work(
            client,
            NamedWorkSpec(
                corpus_id="mussar",
                corpus_seq=1,
                ref_title="Nothing",
                alt_key="Gate",
                granularity=Granularity.GATE,
            ),
        )
