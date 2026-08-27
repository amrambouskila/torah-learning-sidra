from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

RESTORE_WORD = "RESTORE"


class RestoreRequest(BaseModel):
    """Put the ledger back to the safety copy a correction wrote.

    Takes no path. The general "replace my ledger from any file" power stays in the CLI; this reads
    one known file and nothing else, because it exists for exactly one purpose -- undoing a
    backwards correction -- and that is the only destructive button in the app.
    """

    model_config = ConfigDict(extra="forbid")

    confirm: str

    @field_validator("confirm")
    @classmethod
    def _typed_in_full(cls, value: str) -> str:
        if value != RESTORE_WORD:
            raise ValueError(f"type {RESTORE_WORD} to confirm; this replaces every advance on record")
        return value
