import { Link } from "react-router-dom";
import type { ReactElement } from "react";

import { CompressedRail } from "@/components/CompressedRail";
import { DebtBadge } from "@/components/DebtBadge";
import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import { TagPill } from "@/components/TagPill";
import type { TrackRow } from "@/types/TrackRow";
import { startDateLabel } from "@/utils/startDateLabel";

interface TrackCardProps {
  readonly track: TrackRow;
  readonly onAdvance: (track: TrackRow) => void;
  readonly onSetStart: (track: TrackRow) => void;
}

/**
 * One line of learning on the Today screen.
 *
 * The Hebrew name is the headline and the position sits under it; the rail and the badge answer
 * "how far behind" without needing to be read in order.
 */
export function TrackCard({ track, onAdvance, onSetStart }: TrackCardProps): ReactElement {
  const position = track.at ?? track.up_next;
  const canAdvance = !track.is_finished && track.up_next !== null;

  return (
    <li className="card" data-category={track.category}>
      <div className="card__names">
        <HebrewText className="card__title">{track.name_he}</HebrewText>
        <LatinGloss>{track.name_en}</LatinGloss>
      </div>

      <div className="card__position">
        {position === null ? (
          <span className="card__empty">not started</span>
        ) : (
          <>
            <HebrewText className="card__ref">{position.label_he}</HebrewText>
            <LatinGloss>{position.ref}</LatinGloss>
          </>
        )}
      </div>

      <CompressedRail track={track} />
      <DebtBadge track={track} />

      <div className="card__tags">
        {track.tags.map((tag) => (
          <TagPill key={tag} name={tag} />
        ))}
      </div>

      <div className="card__actions">
        <Link className="card__open" to={`/tracks/${track.id}`}>
          Open
        </Link>
        {track.period !== "none" && (
          <button
            type="button"
            className="card__open"
            onClick={() => {
              onSetStart(track);
            }}
          >
            {startDateLabel(track)}
          </button>
        )}
        <button
          type="button"
          className="card__advance"
          disabled={!canAdvance}
          onClick={() => {
            onAdvance(track);
          }}
        >
          {track.is_finished ? "Finished" : "Advance"}
        </button>
      </div>
    </li>
  );
}
