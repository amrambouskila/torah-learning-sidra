from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sidra.catalog.address_scheme import AddressScheme
from sidra.catalog.amud import amud_label_to_index
from sidra.catalog.bavli_amudim import real_amudim
from sidra.catalog.gematria import to_gematria
from sidra.catalog.ref import ADDR_SEPARATOR, to_ref
from sidra.constants import AMUDIM_PER_DAF

AMUD_ALEF_HE = "ע״א"
AMUD_BEIS_HE = "ע״ב"


@dataclass(frozen=True, slots=True)
class ResolvedUnit:
    """One learnable unit, computed from a work's shape array rather than read from a row."""

    seq: int
    addr: tuple[str, ...]
    ref: str
    label_en: str
    label_he: str
    child_count: int | None


def unit_count(scheme: AddressScheme, shape: Sequence[int]) -> int:
    """How many learnable units a work holds, given its shape array."""
    if scheme is AddressScheme.FLAT:
        return len(shape)
    if scheme is AddressScheme.NESTED:
        return sum(shape)
    if scheme is AddressScheme.DAF_AMUD:
        return sum(1 for segment_count in shape if segment_count)
    raise ValueError(f"units of a {AddressScheme.STORED.value} work are rows, not derived from a shape")


def _daf_amud_hebrew(label: str) -> str:
    """``28b`` -> ``כ״ח ע״ב``. The amud marker is a fixed string, not a numeral."""
    index = amud_label_to_index(label)
    daf = index // AMUDIM_PER_DAF + 1
    side = AMUD_BEIS_HE if index % AMUDIM_PER_DAF else AMUD_ALEF_HE
    return f"{to_gematria(daf)} {side}"


def _resolve_addr(scheme: AddressScheme, shape: Sequence[int], seq: int) -> tuple[tuple[str, ...], int | None]:
    if scheme is AddressScheme.FLAT:
        return (str(seq),), shape[seq - 1]

    if scheme is AddressScheme.NESTED:
        consumed = 0
        for chapter_index, chapter_length in enumerate(shape, start=1):
            if seq <= consumed + chapter_length:
                return (str(chapter_index), str(seq - consumed)), None
            consumed += chapter_length
        raise ValueError(f"seq {seq} is out of range")  # pragma: no cover - guarded by the caller

    label = real_amudim(shape)[seq - 1]
    return (label,), shape[amud_label_to_index(label)]


def unit_at(
    ref_title: str,
    scheme: AddressScheme,
    shape: Sequence[int],
    seq: int,
    labels: Sequence[str] | None = None,
    labels_he: Sequence[str] | None = None,
) -> ResolvedUnit:
    """Resolve the ``seq``-th learnable unit of a work.

    ``seq`` is 1-based and counts *real* units. It is **not** the shape index: the index counts
    array slots from zero including empty ones, so for Avodah Zarah the two differ by one, for
    Tamid by 49, and for Nazir the offset changes mid-masechta at its index-65 gap.

    ``labels`` overrides ``label_en`` for works whose unit names cannot be derived from a count,
    such as Orchot Tzadikim's shaarim.
    """
    if scheme is AddressScheme.STORED:
        raise ValueError(f"units of a {AddressScheme.STORED.value} work are rows, not derived from a shape")

    total = unit_count(scheme, shape)
    if not 1 <= seq <= total:
        raise ValueError(f"seq {seq} is out of range for a work of {total} units")

    for name, override in (("labels", labels), ("labels_he", labels_he)):
        if override is not None and len(override) != total:
            raise ValueError(f"{name} has {len(override)} entries but the work holds {total} units")

    addr, child_count = _resolve_addr(scheme, shape, seq)

    if scheme is AddressScheme.DAF_AMUD:
        label_he = _daf_amud_hebrew(addr[0])
    else:
        label_he = ADDR_SEPARATOR.join(to_gematria(int(component)) for component in addr)

    label_en = labels[seq - 1] if labels is not None else ADDR_SEPARATOR.join(addr)
    if labels_he is not None:
        label_he = labels_he[seq - 1]

    return ResolvedUnit(
        seq=seq,
        addr=addr,
        ref=to_ref(ref_title, addr),
        label_en=label_en,
        label_he=label_he,
        child_count=child_count,
    )
