from __future__ import annotations

from pydantic import BaseModel


class VerifyResult(BaseModel):
    """The catalog against the expected counts."""

    matches: bool
    failures: list[str]
    """One sentence per mismatch, exactly as the CLI prints them. Empty when the catalog is good."""
