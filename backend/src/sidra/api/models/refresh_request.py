from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RefreshRequest(BaseModel):
    """Re-crawl Sefaria and write a new snapshot."""

    model_config = ConfigDict(extra="forbid")

    include_links: bool = True
    """The Ein Mishpat export is ~656 MB. Skipping it leaves the catalog complete and the topic
    map absent, which is what a structural check wants."""
