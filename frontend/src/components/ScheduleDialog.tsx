import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import { api } from "@/api/endpoints";
import type { RailUnit } from "@/types/RailUnit";
import type { ScheduleCorrection } from "@/types/ScheduleCorrection";
import type { TrackRow } from "@/types/TrackRow";
import { dayWorth } from "@/utils/dayWorth";

interface ScheduleDialogProps {
  readonly track: TrackRow;
  readonly onConfirm: (correction: ScheduleCorrection) => void;
  readonly onCancel: () => void;
}

/** How many units either side of the scheduled marker the picker offers. */
const RADIUS = 20;

/** Which operand he is answering for. */
type Operand = "started" | "target";

/**
 * Corrects what a track is supposed to be up to.
 *
 * Two operands, put side by side rather than one chosen for him. They agree about today and
 * disagree about every day before it: moving the day it started leaves the opening position the
 * ledger was seeded with standing, while naming the place it should have reached restates it. Only
 * he knows which was wrong, so only he picks.
 *
 * Neither is disabled on any kind of track. "It started on the 25th" is a true and useful thing to
 * say about a parsha track too — it simply moves the schedule by that day's accrual rather than by
 * one unit, which is what the hint under the field is for. Beyond that the operation is its own
 * preview: both routes state an absolute fact and answer with the recomputed row, so he can see
 * where the schedule landed and say it again differently.
 */
export function ScheduleDialog({ track, onConfirm, onCancel }: ScheduleDialogProps): ReactElement {
  const [operand, setOperand] = useState<Operand>("started");
  const [startedOn, setStartedOn] = useState("");
  const [target, setTarget] = useState("");
  const [span, setSpan] = useState<readonly RailUnit[]>([]);

  const scheduled = track.scheduled_at?.corpus_ordinal ?? track.actual_ordinal;
  const first = Math.max(1, scheduled - RADIUS);

  useEffect(() => {
    api
      .rail(track.id, first, Math.min(track.reachable_to, scheduled + RADIUS))
      .then((units) => {
        setSpan(units);
        return units;
      })
      .catch(() => {
        // The list is a convenience; the field below still takes a reference typed by hand.
        setSpan([]);
      });
  }, [track.id, first, scheduled, track.reachable_to]);

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    if (operand === "started") {
      onConfirm({ startedOn });
      return;
    }
    const picked = span.find((unit) => unit.ref === target || unit.label_en === target);
    onConfirm(picked === undefined ? { toRef: target.trim() } : { toOrdinal: picked.ordinal });
  };

  const ready = operand === "started" ? startedOn !== "" : target.trim() !== "";
  // Bound once so the shortcut below narrows: inside a handler the optional chain would never
  // narrow, and its fallback could never run.
  const here = track.at;

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label={`Schedule ${track.name_en}`}>
      <form className="dialog" onSubmit={submit}>
        <header className="dialog__head">
          <HebrewText as="h2" size="headline">
            {track.name_he}
          </HebrewText>
          <LatinGloss>
            {track.scheduled_at === null
              ? track.name_en
              : `scheduled to ${track.scheduled_at.ref}`}
          </LatinGloss>
        </header>

        <p className="dialog__note">Where should this track be today?</p>

        <label className="dialog__field">
          <input
            type="radio"
            name="operand"
            checked={operand === "started"}
            onChange={() => {
              setOperand("started");
            }}
          />
          <span className="eyebrow">It started on</span>
        </label>
        <label className="dialog__field">
          <span className="eyebrow">Started on</span>
          <input
            type="date"
            value={startedOn}
            onChange={(event) => {
              setStartedOn(event.target.value);
              setOperand("started");
            }}
          />
        </label>
        <p className="dialog__hint">{dayWorth(track)}</p>

        <label className="dialog__field">
          <input
            type="radio"
            name="operand"
            checked={operand === "target"}
            onChange={() => {
              setOperand("target");
            }}
          />
          <span className="eyebrow">It should be at</span>
        </label>
        <label className="dialog__field">
          <span className="eyebrow">Should be at</span>
          <input
            value={target}
            placeholder={track.scheduled_at?.label_en ?? ""}
            onChange={(event) => {
              setTarget(event.target.value);
              setOperand("target");
            }}
          />
        </label>

        {here !== null && (
          <button
            type="button"
            className="dialog__catchup"
            onClick={() => {
              setTarget(here.ref);
              setOperand("target");
            }}
          >
            I&apos;m up to date ({here.label_en})
          </button>
        )}

        <footer className="dialog__actions">
          <button type="button" className="dialog__cancel" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="dialog__confirm" disabled={!ready}>
            Set schedule
          </button>
        </footer>
      </form>
    </div>
  );
}
