import type { TrackRow } from "./TrackRow";

export interface AdvanceResult {
  /** Null when the request was a replay and nothing was written. */
  readonly advance_id: string | null;
  /** Where the request resolved to, written or not. On a replay this is what was refused. */
  readonly resolved_ordinal: number;
  readonly from_ordinal: number;
  readonly to_ordinal: number;
  readonly unit_count: number;
  readonly was_replay: boolean;
  readonly track: TrackRow;
}
