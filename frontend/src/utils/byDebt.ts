import type { TrackRow } from "@/types/TrackRow";

/**
 * Most behind first, because Today answers "what do I owe".
 *
 * A track that has not started sorts last however large its nominal debt: it owes nothing yet, and
 * putting it above a real debt would be a lie about what needs attention.
 */
export function byDebt(left: TrackRow, right: TrackRow): number {
  const rank = (row: TrackRow): number => {
    if (row.starts_in_days !== null) return -1;
    if (row.debt !== null) return row.debt;
    return row.days_stale ?? Number.MAX_SAFE_INTEGER;
  };
  const difference = rank(right) - rank(left);
  return difference !== 0 ? difference : left.name_en.localeCompare(right.name_en);
}
