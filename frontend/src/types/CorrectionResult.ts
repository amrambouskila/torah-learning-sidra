import type { TrackRow } from "./TrackRow";

/** What one backwards correction did, and the track as it now stands. */
export interface CorrectionResult {
  readonly from_ordinal: number;
  readonly to_ordinal: number;
  /** How far the position dropped — what the toast reports. */
  readonly removed_units: number;
  /** Rows deleted outright. A row trimmed rather than deleted is not counted. */
  readonly removed_advances: number;
  /** False when the destination was already the position and nothing was written. */
  readonly moved: boolean;
  readonly track: TrackRow;
}
