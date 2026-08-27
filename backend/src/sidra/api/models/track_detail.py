from __future__ import annotations

from pydantic import BaseModel

from sidra.api.models.rail_unit import RailUnit
from sidra.api.models.track_row import TrackRow


class TrackDetail(BaseModel):
    """One track with a window of its rail around the two markers.

    The rail is windowed rather than whole: the Shulchan Aruch track holds 1,705 simanim and the
    Mishneh Torah chavrusa tracks 15,143 halachos, so serving every unit would make the detail view
    the heaviest response in the app for no gain.
    """

    track: TrackRow
    rail: list[RailUnit]
    rail_from: int
    rail_to: int
