import type { TrackRow } from "@/types/TrackRow";

/**
 * What one step of the calendar is worth on this track.
 *
 * Moving the day a schedule started shifts it by whole periods, and a period is not one unit
 * everywhere: the parsha tracks take their pace from the calendar, so a combined week hands out
 * two. Saying so under the date field is what lets him see whether the day he picked lands where
 * he wants, without the app having to guess which operand he meant.
 */
export function dayWorth(track: TrackRow): string {
  if (track.kind === "parsha_aliyah") return "one day is 1 aliyah here, 2 in a combined week";
  if (track.kind === "parsha_weekly") return "one week is 1 unit here, 2 in a combined week";
  const noun = track.rate === 1 ? track.unit_singular : track.unit_plural;
  const span = track.period === "week" ? "week" : "day";
  return `one ${span} is ${String(track.rate)} ${noun} here`;
}
