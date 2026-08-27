import type { ReactElement } from "react";

import type { TrackRow } from "@/types/TrackRow";
import { inCycle } from "@/utils/inCycle";

interface CompressedRailProps {
  readonly track: TrackRow;
}

const SEGMENTS = 40;

/**
 * The whole spine squeezed into one row: the same two markers as the Track screen, at a scale
 * where the gap between them is a glance rather than a scroll.
 *
 * Fixed at forty segments so every row on Today lines up, whatever its track's length.
 */
export function CompressedRail({ track }: CompressedRailProps): ReactElement {
  const total = Math.max(track.total, 1);
  // A cycle track's ordinals run past the end of the cycle; the bar shows the turn he is in.
  const here = inCycle(track, track.actual_ordinal);
  const actual = Math.round((here / total) * SEGMENTS);
  const scheduledOrdinal = track.scheduled_at?.corpus_ordinal ?? null;
  const scheduled =
    scheduledOrdinal === null ? null : Math.round((inCycle(track, scheduledOrdinal) / total) * SEGMENTS);
  const where = `${String(here)} of ${String(track.total)}`;

  return (
    <span
      className="mini"
      role="img"
      aria-label={
        scheduledOrdinal === null ? where : `${where}, scheduled ${String(scheduledOrdinal)}`
      }
    >
      {Array.from({ length: SEGMENTS }, (_, index) => {
        const position = index + 1;
        const state =
          scheduled !== null && position === scheduled
            ? "scheduled"
            : position <= actual
              ? "done"
              : scheduled !== null && position < scheduled
                ? "between"
                : "ahead";
        return <i key={position} className="mini__tick" data-state={state} />;
      })}
    </span>
  );
}
