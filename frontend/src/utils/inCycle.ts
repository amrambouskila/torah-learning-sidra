import type { TrackRow } from "@/types/TrackRow";

/**
 * Where a position sits inside the turn it belongs to.
 *
 * A cycle track's ordinals keep counting past the end of the cycle -- that is what carries the
 * debt across Simchat Torah instead of freezing it. Only the *display* folds back.
 */
export function inCycle(track: TrackRow, ordinal: number): number {
  if (track.cycle_length === null || ordinal < 1) return ordinal;
  return ((ordinal - 1) % track.cycle_length) + 1;
}
