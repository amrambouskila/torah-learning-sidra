import type { TrackRow } from "@/types/TrackRow";

/** What the control offers: declaring a start date for the first time, or moving one. */
export function startDateLabel(track: TrackRow): string {
  return track.starts_on === null ? "Set start" : "Start date";
}
