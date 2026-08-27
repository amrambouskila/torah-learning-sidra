from __future__ import annotations

import uuid

from pydantic import BaseModel

from sidra.api.models.position_model import PositionModel
from sidra.api.models.sequence_stage import SequenceStage


class SequenceResponse(BaseModel):
    """Which masechta the code asks for next, and how far off it is."""

    track_id: uuid.UUID
    name_en: str
    name_he: str

    at: PositionModel | None
    """Where the code-learning stands. None on a track never opened."""

    stages: list[SequenceStage]
