import type { RailUnit } from "./RailUnit";
import type { TrackRow } from "./TrackRow";

export interface TrackDetail {
  readonly track: TrackRow;
  readonly rail: readonly RailUnit[];
  readonly rail_from: number;
  readonly rail_to: number;
}
