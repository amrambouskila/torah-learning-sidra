import type { RailState } from "@/types/RailState";

/** Which of the five states a unit is in, given the two markers. */
export function railState(ordinal: number, actual: number, scheduled: number | null): RailState {
  if (ordinal === actual) return "actual";
  if (scheduled !== null && ordinal === scheduled) return "scheduled";
  if (ordinal < actual) return "done";
  if (scheduled !== null && ordinal < scheduled) return "between";
  return "ahead";
}
