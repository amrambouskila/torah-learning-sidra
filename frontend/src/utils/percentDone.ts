import type { TrackRow } from "@/types/TrackRow";

import { inCycle } from "./inCycle";

/** How far through the current turn, rounded. Zero total is a track with nothing in it. */
export function percentDone(track: TrackRow): number {
  if (track.total === 0) return 0;
  return Math.round((inCycle(track, track.actual_ordinal) / track.total) * 100);
}
