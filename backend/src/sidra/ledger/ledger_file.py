"""Read and write the ledger document.

Pretty-printed JSON with sorted keys, so two exports of the same ledger are byte-identical and a
diff between them reads as a list of what changed rather than one reflowed line.
"""

from __future__ import annotations

import json
from pathlib import Path

from sidra.ledger.ledger_document import MAX_BYTES, LedgerDocument

LEDGER_PATH = Path(__file__).resolve().parents[3] / "data" / "ledger.json"


def write_ledger(path: Path, document: LedgerDocument) -> None:
    """Write the ledger. Two writes of the same document are byte-identical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(document.model_dump_json())
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def read_ledger(path: Path) -> LedgerDocument:
    """Read a ledger back, validating it as untrusted input.

    Size is checked before the file is read: a strict model refuses bad *shapes*, but only a cap
    refuses a file too large to hold in memory in the first place.
    """
    if not path.exists():
        raise ValueError(f"{path}: no ledger export here; run 'sidra-db export' on the old machine")
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise ValueError(f"{path}: {size} bytes exceeds the {MAX_BYTES}-byte ledger cap")

    try:
        document = LedgerDocument.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(f"{path}: not a valid ledger export ({error})") from error

    document.check_references()
    return document
