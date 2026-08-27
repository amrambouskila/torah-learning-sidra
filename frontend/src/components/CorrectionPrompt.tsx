import { type ReactElement } from "react";

import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import type { TrackRow } from "@/types/TrackRow";
import { correctionPhrase } from "@/utils/correctionPhrase";

interface CorrectionPromptProps {
  readonly track: TrackRow;
  /** Where he says he really is. Always behind ``track.actual_ordinal``. */
  readonly toOrdinal: number;
  /** How the place was named — the ref he typed, or the address he clicked. */
  readonly label: string;
  readonly onConfirm: () => void;
  readonly onCancel: () => void;
}

/**
 * Asks before moving a track backwards.
 *
 * Reached two ways, and both of them are moments where he has said a place rather than chosen an
 * operation: a reference typed into the advance dialog that turned out to be behind him, and a
 * click on a rail node he has already passed. Neither reads as destructive on its own, so the cost
 * is named here before anything is deleted.
 */
export function CorrectionPrompt({
  track,
  toOrdinal,
  label,
  onConfirm,
  onCancel,
}: CorrectionPromptProps): ReactElement {
  return (
    <div
      className="overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Correct ${track.name_en}`}
    >
      <div className="dialog">
        <header className="dialog__head">
          <HebrewText as="h2" size="headline">
            {track.name_he}
          </HebrewText>
          <LatinGloss>{`now at ${track.at?.ref ?? track.name_en}`}</LatinGloss>
        </header>

        <p className="dialog__note">Correcting to {label}</p>
        <p className="dialog__warning">{correctionPhrase(track, track.actual_ordinal, toOrdinal)}</p>

        <footer className="dialog__actions">
          <button type="button" className="dialog__cancel" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="dialog__confirm" onClick={onConfirm}>
            Correct position
          </button>
        </footer>
      </div>
    </div>
  );
}
