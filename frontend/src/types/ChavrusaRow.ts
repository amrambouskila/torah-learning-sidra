import type { SessionRow } from "./SessionRow";
import type { TrackRow } from "./TrackRow";

export interface ChavrusaRow {
  readonly id: string;
  readonly name: string;
  readonly notes: string | null;
  /** Null if they have never met. Such a chavrusa sorts above any measured staleness. */
  readonly days_stale: number | null;
  readonly tracks: readonly TrackRow[];
  readonly sessions: readonly SessionRow[];
}
