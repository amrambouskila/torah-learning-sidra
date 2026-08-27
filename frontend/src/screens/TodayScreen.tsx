import { useEffect, useMemo, useState, type ReactElement } from "react";

import { AdvanceDialog } from "@/components/AdvanceDialog";
import { CorrectionPrompt } from "@/components/CorrectionPrompt";
import { StartDateDialog } from "@/components/StartDateDialog";
import { ErrorBanner } from "@/components/ErrorBanner";
import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import { TagPill } from "@/components/TagPill";
import { TrackCard } from "@/components/TrackCard";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { pushToast } from "@/stores/toastSlice";
import { loadToday } from "@/stores/todaySlice";
import { advanceTrack, correctPosition, setTrackStart } from "@/stores/tracksSlice";
import type { AdvanceDestination } from "@/types/AdvanceDestination";
import type { Category } from "@/types/Category";
import type { TrackRow } from "@/types/TrackRow";
import { byDebt } from "@/utils/byDebt";
import { failureMessage } from "@/utils/failureMessage";

const GROUPS: readonly { key: Category; title: string; hebrew: string }[] = [
  { key: "daily", title: "Daily", hebrew: "יומי" },
  { key: "shabbat", title: "Shabbat", hebrew: "שבת" },
  { key: "chavrusa", title: "Chavrusa", hebrew: "חברותא" },
];

export function TodayScreen(): ReactElement {
  const dispatch = useAppDispatch();
  const { data, status, error, isConflict } = useAppSelector((state) => state.today);
  const [filter, setFilter] = useState<string | null>(null);
  const [advancing, setAdvancing] = useState<TrackRow | null>(null);
  const [starting, setStarting] = useState<TrackRow | null>(null);
  const [correcting, setCorrecting] = useState<{
    readonly track: TrackRow;
    readonly toOrdinal: number;
    readonly label: string;
  } | null>(null);

  useEffect(() => {
    void dispatch(loadToday(undefined));
  }, [dispatch]);

  const tags = useMemo(() => {
    if (data === null) return [];
    const rows = [...data.daily, ...data.shabbat, ...data.chavrusa];
    return [...new Set(rows.flatMap((row) => row.tags))].sort();
  }, [data]);

  const correct = (track: TrackRow, toOrdinal: number, label: string): void => {
    setCorrecting(null);
    void dispatch(correctPosition({ trackId: track.id, destination: { toOrdinal }, confirm: true }))
      .unwrap()
      .then((result) => {
        dispatch(
          pushToast(
            `${track.name_en} back to ${result.track.at?.ref ?? label} — ${result.removed_units} removed.`,
            "success",
          ),
        );
        return dispatch(loadToday(undefined));
      })
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, "The correction was not made."), "failure"));
      });
  };

  const confirm = (
    track: TrackRow,
    destination: AdvanceDestination,
    label: string,
    note: string | undefined,
  ): void => {
    setAdvancing(null);
    // A picked unit carries its ordinal, so which way it goes is settled here rather than by
    // posting an advance and reading a replay back.
    if ("toOrdinal" in destination && destination.toOrdinal < track.actual_ordinal) {
      correct(track, destination.toOrdinal, label);
      return;
    }
    void dispatch(advanceTrack({ trackId: track.id, destination, ...(note === undefined ? {} : { note }) }))
      .unwrap()
      .then((result) => {
        // A reference only reveals its direction once the server has resolved it, so a replay
        // that landed behind him is an offer to correct rather than a shrug.
        if (result.was_replay && result.resolved_ordinal < track.actual_ordinal) {
          setCorrecting({ track, toOrdinal: result.resolved_ordinal, label });
          return result;
        }
        dispatch(
          pushToast(
            result.was_replay
              ? `${track.name_en} was already there.`
              : `${track.name_en} advanced to ${result.track.at?.ref ?? label}.`,
            result.was_replay ? "info" : "success",
          ),
        );
        void dispatch(loadToday(undefined));
        return result;
      })
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, "The advance was not recorded."), "failure"));
      });
  };

  const saveStart = (track: TrackRow, startsOn: string | null, forgive: boolean): void => {
    setStarting(null);
    void dispatch(setTrackStart({ trackId: track.id, startsOn, forgive }))
      .unwrap()
      .then((row) => {
        dispatch(
          pushToast(
            row.starts_on === null
              ? `${track.name_en} starts now.`
              : `${track.name_en} starts ${row.starts_on}.`,
            "success",
          ),
        );
        return dispatch(loadToday(undefined));
      })
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, "The start date was not saved."), "failure"));
      });
  };

  if (status === "failed" && error !== null) {
    return (
      <section className="screen">
        <h1 className="screen__title">Today</h1>
        <ErrorBanner message={error} isConflict={isConflict} />
      </section>
    );
  }

  if (data === null) {
    return (
      <section className="screen">
        <h1 className="screen__title">Today</h1>
        <p className="screen__lede">Loading the sidra…</p>
      </section>
    );
  }

  return (
    <section className="screen">
      <header className="today__head">
        <div>
          <h1 className="screen__title">Today</h1>
          <p className="screen__lede">
            <HebrewText className="today__date">{data.hebrew_date}</HebrewText>{" "}
            <LatinGloss>{data.civil_date}</LatinGloss>
            {data.parsha_he.length > 0 && (
              <>
                {" · "}
                <HebrewText className="today__parsha">{data.parsha_he.join(" · ")}</HebrewText>{" "}
                <LatinGloss>{data.parsha_en.join("-")}</LatinGloss>
              </>
            )}
            {data.is_yom_tov && <span className="today__yomtov">Yom Tov</span>}
          </p>
        </div>
        {tags.length > 0 && (
          <div className="today__filters">
            <span className="eyebrow">Filter</span>
            {tags.map((tag) => (
              <TagPill
                key={tag}
                name={tag}
                active={filter === tag}
                onClick={() => {
                  setFilter(filter === tag ? null : tag);
                }}
              />
            ))}
          </div>
        )}
      </header>

      {GROUPS.map((group) => {
        const rows = [...data[group.key]]
          .filter((row) => filter === null || row.tags.includes(filter))
          .sort(byDebt);
        if (rows.length === 0) return null;
        return (
          <section key={group.key} className="group" data-category={group.key}>
            <h2 className="group__title">
              <HebrewText size="headline">{group.hebrew}</HebrewText>
              <LatinGloss>{group.title}</LatinGloss>
            </h2>
            <ul className="group__list">
              {rows.map((row) => (
                <TrackCard key={row.id} track={row} onAdvance={setAdvancing} onSetStart={setStarting} />
              ))}
            </ul>
          </section>
        );
      })}

      {correcting !== null && (
        <CorrectionPrompt
          track={correcting.track}
          toOrdinal={correcting.toOrdinal}
          label={correcting.label}
          onConfirm={() => {
            correct(correcting.track, correcting.toOrdinal, correcting.label);
          }}
          onCancel={() => {
            setCorrecting(null);
          }}
        />
      )}

      {starting !== null && (
        <StartDateDialog
          track={starting}
          today={data.civil_date}
          onConfirm={(startsOn, forgive) => {
            saveStart(starting, startsOn, forgive);
          }}
          onCancel={() => {
            setStarting(null);
          }}
        />
      )}

      {advancing !== null && (
        <AdvanceDialog
          track={advancing}
          onConfirm={(destination, label, note) => {
            confirm(advancing, destination, label, note);
          }}
          onCancel={() => {
            setAdvancing(null);
          }}
        />
      )}
    </section>
  );
}
