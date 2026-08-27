import { useEffect, useState, type ReactElement } from "react";
import { useParams } from "react-router-dom";

import { CorrectionPrompt } from "@/components/CorrectionPrompt";
import { DebtBadge } from "@/components/DebtBadge";
import { ErrorBanner } from "@/components/ErrorBanner";
import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import { Numeral } from "@/components/Numeral";
import { Rail } from "@/components/Rail";
import { StartDateDialog } from "@/components/StartDateDialog";
import { ScheduleDialog } from "@/components/ScheduleDialog";
import { SefariaLink } from "@/components/SefariaLink";
import { TagPill } from "@/components/TagPill";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { pushToast } from "@/stores/toastSlice";
import { loadTags } from "@/stores/tagsSlice";
import { advanceTrack, correctPosition, correctSchedule, setTrackStart, setTrackTags } from "@/stores/tracksSlice";
import type { ScheduleCorrection } from "@/types/ScheduleCorrection";
import type { TrackRow } from "@/types/TrackRow";
import { api } from "@/api/endpoints";
import { failureMessage } from "@/utils/failureMessage";
import { inCycle } from "@/utils/inCycle";
import { percentDone } from "@/utils/percentDone";
import { startDateLabel } from "@/utils/startDateLabel";

export function TrackScreen(): ReactElement {
  const { trackId = "" } = useParams();
  const dispatch = useAppDispatch();
  const [track, setTrack] = useState<TrackRow | null>(null);
  const [error, setError] = useState<{ message: string; isConflict: boolean } | null>(null);
  const [editingStart, setEditingStart] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState(false);
  const [correcting, setCorrecting] = useState<{ readonly toOrdinal: number; readonly label: string } | null>(
    null,
  );
  const allTags = useAppSelector((state) => state.tags.data);

  useEffect(() => {
    void dispatch(loadTags());
  }, [dispatch]);

  const refresh = (): void => {
    api
      .track(trackId, { radius: 0 })
      .then((detail) => {
        setTrack(detail.track);
        setError(null);
        return detail;
      })
      .catch((caught: unknown) => {
        const message = failureMessage(caught, "The track could not be loaded.");
        setError({ message, isConflict: message.includes("calendar") });
      });
  };

  useEffect(refresh, [trackId]);

  /**
   * Tags are sent as the whole set the track should wear rather than as a change to it, so two
   * quick toggles cannot interleave into a state neither of them meant.
   */
  const toggleTag = (row: TrackRow, name: string): void => {
    const wanted = row.tags.includes(name)
      ? row.tags.filter((existing) => existing !== name)
      : [...row.tags, name];
    const ids = allTags.filter((tag) => wanted.includes(tag.name)).map((tag) => tag.id);
    void dispatch(setTrackTags({ trackId, tagIds: ids }))
      .unwrap()
      .then((updated) => {
        setTrack(updated);
        return updated;
      })
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, "The tag was not changed."), "failure"));
      });
  };

  const correct = (toOrdinal: number, label: string): void => {
    setCorrecting(null);
    void dispatch(correctPosition({ trackId, destination: { toOrdinal }, confirm: true }))
      .unwrap()
      .then((result) => {
        setTrack(result.track);
        dispatch(
          pushToast(
            `Back to ${result.track.at?.ref ?? label} — ${result.removed_units} removed.`,
            "success",
          ),
        );
        return result;
      })
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, "The correction was not made."), "failure"));
      });
  };

  const saveSchedule = (correction: ScheduleCorrection): void => {
    setEditingSchedule(false);
    void dispatch(correctSchedule({ trackId, correction }))
      .unwrap()
      .then((row) => {
        setTrack(row);
        dispatch(pushToast(`Scheduled to ${row.scheduled_at?.ref ?? "the start"}.`, "success"));
        return row;
      })
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, "The schedule was not changed."), "failure"));
      });
  };

  /**
   * A click on the rail. The node already knows its ordinal, so which way it goes is settled here
   * rather than by asking the server and reading a replay back.
   */
  const select = (ordinal: number, row: TrackRow): void => {
    if (ordinal < row.actual_ordinal) {
      setCorrecting({ toOrdinal: ordinal, label: `unit ${ordinal}` });
      return;
    }
    void dispatch(advanceTrack({ trackId, destination: { toOrdinal: ordinal } }))
      .unwrap()
      .then((result) => {
        setTrack(result.track);
        dispatch(
          pushToast(
            result.was_replay
              ? "Already there."
              : `Moved to ${result.track.at?.ref ?? "the new position"}.`,
            result.was_replay ? "info" : "success",
          ),
        );
        return result;
      })
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, "That did not work."), "failure"));
      });
  };

  const saveStart = (startsOn: string | null, forgive: boolean): void => {
    setEditingStart(false);
    void dispatch(setTrackStart({ trackId, startsOn, forgive }))
      .unwrap()
      .then((row) => {
        setTrack(row);
        dispatch(
          pushToast(row.starts_on === null ? "Started now." : `Starts ${row.starts_on}.`, "success"),
        );
        return row;
      })
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, "The start date was not saved."), "failure"));
      });
  };

  if (error !== null) {
    return (
      <section className="screen">
        <h1 className="screen__title">Track</h1>
        <ErrorBanner message={error.message} isConflict={error.isConflict} />
      </section>
    );
  }

  if (track === null) {
    return (
      <section className="screen">
        <p className="screen__lede">Loading the rail…</p>
      </section>
    );
  }

  const position = track.at ?? track.up_next;

  return (
    <section className="screen" data-category={track.category}>
      <header className="track__head">
        <div>
          <HebrewText as="h1" size="display">
            {track.name_he}
          </HebrewText>
          <LatinGloss>{track.name_en}</LatinGloss>
        </div>
        <div className="track__head-right">
          <DebtBadge track={track} />
          {track.period !== "none" && (
            <button
              type="button"
              className="card__open"
              onClick={() => {
                setEditingStart(true);
              }}
            >
              {startDateLabel(track)}
            </button>
          )}
          {track.period !== "none" && (
            <button
              type="button"
              className="card__open"
              onClick={() => {
                setEditingSchedule(true);
              }}
            >
              Schedule
            </button>
          )}
        </div>
      </header>

      <dl className="track__facts">
        <div>
          <dt className="eyebrow">Where you are</dt>
          <dd>
            {position === null ? (
              <span className="card__empty">not started</span>
            ) : (
              <>
                <HebrewText>{position.label_he}</HebrewText>{" "}
                <SefariaLink url={position.sefaria_url} label={position.ref} />
              </>
            )}
          </dd>
        </div>
        <div>
          <dt className="eyebrow">Scheduled</dt>
          <dd>
            {track.scheduled_at === null ? (
              <span className="card__empty">no schedule</span>
            ) : (
              <SefariaLink url={track.scheduled_at.sefaria_url} label={track.scheduled_at.ref} />
            )}
          </dd>
        </div>
        <div>
          <dt className="eyebrow">Starts</dt>
          <dd>
            {track.starts_on === null ? (
              <span className="card__empty">no start date</span>
            ) : (
              <Numeral>{track.starts_on}</Numeral>
            )}
          </dd>
        </div>
        <div>
          <dt className="eyebrow">Progress</dt>
          <dd>
            <Numeral>{`${String(percentDone(track))}%`}</Numeral>{" "}
            <span className="track__of">
              <Numeral>{inCycle(track, track.actual_ordinal)}</Numeral> of{" "}
              <Numeral>{track.total}</Numeral> {track.unit_plural}
              {track.cycle_index !== null && track.cycle_index > 1 && (
                <> · time {track.cycle_index} round</>
              )}
            </span>
          </dd>
        </div>
      </dl>

      <div className="track__tags">
        <span className="eyebrow">Tags</span>
        <div className="track__tagrow">
          {allTags.length === 0 ? (
            <span className="track__notags">
              No tags yet — make one on the Tags screen and it will appear here.
            </span>
          ) : (
            allTags.map((tag) => (
              <TagPill
                key={tag.id}
                name={tag.name}
                color={tag.color}
                active={track.tags.includes(tag.name)}
                onClick={() => {
                  toggleTag(track, tag.name);
                }}
              />
            ))
          )}
        </div>
      </div>

      <Rail
        trackId={track.id}
        total={track.reachable_to}
        actual={track.actual_ordinal}
        scheduled={track.scheduled_at?.corpus_ordinal ?? null}
        onSelect={(ordinal) => {
          select(ordinal, track);
        }}
      />

      {correcting !== null && (
        <CorrectionPrompt
          track={track}
          toOrdinal={correcting.toOrdinal}
          label={correcting.label}
          onConfirm={() => {
            correct(correcting.toOrdinal, correcting.label);
          }}
          onCancel={() => {
            setCorrecting(null);
          }}
        />
      )}

      {editingSchedule && (
        <ScheduleDialog
          track={track}
          onConfirm={saveSchedule}
          onCancel={() => {
            setEditingSchedule(false);
          }}
        />
      )}

      {editingStart && (
        <StartDateDialog
          track={track}
          today={new Date().toISOString().slice(0, 10)}
          onConfirm={saveStart}
          onCancel={() => {
            setEditingStart(false);
          }}
        />
      )}
    </section>
  );
}
