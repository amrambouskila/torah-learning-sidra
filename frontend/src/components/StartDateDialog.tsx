import { useState, type FormEvent, type ReactElement } from "react";

import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import type { TrackRow } from "@/types/TrackRow";

interface StartDateDialogProps {
  readonly track: TrackRow;
  /** Today, ISO, so the picker cannot offer a day the server would refuse. */
  readonly today: string;
  readonly onConfirm: (startsOn: string | null, forgive: boolean) => void;
  readonly onCancel: () => void;
}

const PRESETS: readonly { readonly label: string; readonly days: number }[] = [
  { label: "Tomorrow", days: 1 },
  { label: "In a week", days: 7 },
  { label: "In two weeks", days: 14 },
  { label: "In a month", days: 30 },
];

function shift(iso: string, days: number): string {
  const day = new Date(`${iso}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + days);
  return day.toISOString().slice(0, 10);
}

/**
 * Choose the day a track's schedule begins.
 *
 * Setting one forgives what the track ran up while it sat unopened, which is the point: a sefer
 * you have not started should be waiting, not quietly accumulating a debt you never owed.
 */
export function StartDateDialog({
  track,
  today,
  onConfirm,
  onCancel,
}: StartDateDialogProps): ReactElement {
  const [startsOn, setStartsOn] = useState(track.starts_on ?? shift(today, 7));

  // A backlog is only real once the track has actually been opened. A sefer seeded at its
  // first unit has a position but owes nothing, and clearing nothing needs no warning.
  const owed = track.actual_ordinal > 0 && track.debt !== null && track.debt > 0 ? track.debt : 0;
  const noun = owed === 1 ? track.unit_singular : track.unit_plural;

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    onConfirm(startsOn, owed > 0);
  };

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label={`Start date for ${track.name_en}`}>
      <form className="dialog" onSubmit={submit}>
        <header className="dialog__head">
          <HebrewText as="h2" size="headline">
            {track.name_he}
          </HebrewText>
          <LatinGloss>{track.name_en}</LatinGloss>
        </header>

        <p className="dialog__note">
          Until this day the track waits: no debt, just a countdown. The day itself is a learning
          day, so the first {track.unit_singular} is due on it.
        </p>

        <label className="dialog__field">
          <span className="eyebrow">Starts on</span>
          <input
            type="date"
            min={today}
            value={startsOn}
            onChange={(event) => {
              setStartsOn(event.target.value);
            }}
          />
        </label>

        {owed > 0 && (
          <p className="dialog__warn">
            {track.name_en} owes {owed} {noun}. Setting a start date clears that.
          </p>
        )}

        <div className="dialog__presets">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className="dialog__catchup"
              onClick={() => {
                setStartsOn(shift(today, preset.days));
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <footer className="dialog__actions">
          {track.starts_on !== null && (
            <button
              type="button"
              className="dialog__clear"
              onClick={() => {
                onConfirm(null, false);
              }}
            >
              Start it now
            </button>
          )}
          <button type="button" className="dialog__cancel" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="dialog__confirm">
            {owed > 0 ? `Clear ${String(owed)} and save` : "Save"}
          </button>
        </footer>
      </form>
    </div>
  );
}
