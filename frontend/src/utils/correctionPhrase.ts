import type { TrackRow } from "@/types/TrackRow";

/**
 * What a backwards correction is about to cost, in this track's own units.
 *
 * Spelled out rather than left to a bare "are you sure": the operation deletes recorded learning
 * and cannot be undone, so the number and the noun both belong in front of him before he confirms.
 */
export function correctionPhrase(track: TrackRow, from: number, to: number): string {
  const dropped = from - to;
  const noun = dropped === 1 ? track.unit_singular : track.unit_plural;
  return `That is ${dropped} ${noun} behind where you are. Correcting removes ${dropped} ${noun} of recorded learning, and there is no undo.`;
}
