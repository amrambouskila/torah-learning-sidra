import type { TrackRow } from "@/types/TrackRow";

export type DebtTone = "behind" | "ahead" | "level" | "waiting" | "stale" | "done";

export interface DebtPhrase {
  readonly tone: DebtTone;
  readonly value: string;
  readonly suffix: string;
}

/**
 * The one place a track's standing becomes words.
 *
 * Order matters: a track that has not started is not "level", and a finished track is not "behind"
 * however long ago it finished.
 */
export function debtPhrase(track: TrackRow): DebtPhrase {
  if (track.starts_in_days !== null) {
    // Days inside the first week: rounding three days up to "1 week away" was harmless when the
    // only start dates were seven weeks out, and wrong the moment a date can be picked.
    const days = track.starts_in_days;
    if (days < 7) return { tone: "waiting", value: String(days), suffix: days === 1 ? "day away" : "days away" };
    const weeks = Math.ceil(days / 7);
    return { tone: "waiting", value: String(weeks), suffix: weeks === 1 ? "week away" : "weeks away" };
  }
  if (track.is_finished) return { tone: "done", value: "", suffix: "finished" };

  if (track.debt === null) {
    if (track.days_stale === null) return { tone: "stale", value: "", suffix: "never learned" };
    const weeks = Math.floor(track.days_stale / 7);
    if (weeks >= 1) return { tone: "stale", value: String(weeks), suffix: weeks === 1 ? "week since" : "weeks since" };
    return { tone: "stale", value: String(track.days_stale), suffix: track.days_stale === 1 ? "day since" : "days since" };
  }

  if (track.debt > 0) {
    const noun = track.debt === 1 ? track.unit_singular : track.unit_plural;
    return { tone: "behind", value: String(track.debt), suffix: `${noun} behind` };
  }
  if (track.days_ahead > 0) {
    return { tone: "ahead", value: String(track.days_ahead), suffix: track.days_ahead === 1 ? "day ahead" : "days ahead" };
  }
  return { tone: "level", value: "", suffix: "on pace" };
}
