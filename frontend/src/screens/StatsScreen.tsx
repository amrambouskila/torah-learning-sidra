import { useEffect, useState, type ReactElement } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { HebrewText } from "@/components/HebrewText";
import { Numeral } from "@/components/Numeral";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { loadStats } from "@/stores/statsSlice";
import type { StatsTrack } from "@/types/StatsResponse";

const WINDOWS: readonly number[] = [7, 30, 90];

/** How a day's cell reads. The ledger's own question, not "did you show up". */
function cellState(net: number): "closed" | "held" | "opened" {
  if (net < 0) return "closed";
  return net > 0 ? "opened" : "held";
}

function movement(track: StatsTrack): string {
  if (track.debt_now === null || track.debt_then === null) return "—";
  const change = track.debt_now - track.debt_then;
  if (change === 0) return "held";
  const noun = Math.abs(change) === 1 ? track.unit_singular : track.unit_plural;
  return change < 0
    ? `closed ${String(-change)} ${noun}`
    : `opened ${String(change)} ${noun}`;
}

/** One cell per day of the window. A day the server sent no value for held, by definition. */
function cells(days: readonly string[], net: readonly number[]): readonly { day: string; net: number }[] {
  return days.map((day, index) => ({ day, net: net[index] ?? 0 }));
}

/** Most neglected first: opened but idle longest, then never opened, then the rest. */
function byNeglect(left: StatsTrack, right: StatsTrack): number {
  const idle = (track: StatsTrack): number => (track.days_learned === 0 ? 1 : 0);
  if (idle(left) !== idle(right)) return idle(right) - idle(left);
  const debt = (track: StatsTrack): number => track.debt_now ?? -Infinity;
  if (debt(left) !== debt(right)) return debt(right) - debt(left);
  return left.name_en.localeCompare(right.name_en);
}

/**
 * Stats: whether the gap is opening or closing.
 *
 * A habit tracker asks "did you show up?"; a debt ledger asks whether the gap is opening or
 * closing, so every cell carries a signed quantity rather than a tick. That is also what makes
 * the grid honest on a young ledger — every begun track has a true value on every day it has
 * existed, so a three-day ledger draws three real columns rather than ninety mostly-grey ones.
 */
export function StatsScreen(): ReactElement {
  const dispatch = useAppDispatch();
  const { data, status, error, isConflict } = useAppSelector((state) => state.stats);
  const [windowDays, setWindowDays] = useState(30);

  useEffect(() => {
    void dispatch(loadStats(windowDays));
  }, [dispatch, windowDays]);

  const clamped = data !== null && data.window_days < data.requested_window_days;
  const tracks = data === null ? [] : [...data.tracks].sort(byNeglect);

  return (
    <section className="screen">
      <h1 className="screen__title">Stats</h1>
      <p className="screen__lede">
        Not whether you showed up — whether the gap is opening or closing. Each cell is what the
        schedule billed that day minus what you learned, so a track that keeps its pace reads flat
        whether that is one amud or fourteen aliyot.
      </p>

      {status === "failed" && error !== null && <ErrorBanner message={error} isConflict={isConflict} />}

      {data !== null && (
        <>
          <div className="stats__standing">
            {(
              [
                ["behind", data.standing.behind],
                ["on pace", data.standing.on_pace],
                ["ahead", data.standing.ahead],
                ["waiting", data.standing.not_started],
                ["chavrusa", data.standing.chavrusa],
              ] as const
            ).map(([label, count]) => (
              <div key={label} className="stats__count" data-bucket={label}>
                <Numeral>{count}</Numeral>
                <span className="eyebrow">{label}</span>
              </div>
            ))}
            <div className="stats__count stats__count--streak">
              <Numeral>{data.streak.current}</Numeral>
              <span className="eyebrow">
                day{data.streak.current === 1 ? "" : "s"} running
                {data.streak.longest > data.streak.current && (
                  <> · best {data.streak.longest}</>
                )}
              </span>
            </div>
          </div>

          <div className="stats__knobs">
            <span className="eyebrow">Last</span>
            {WINDOWS.map((option) => (
              <button
                key={option}
                type="button"
                className="pill pill--button"
                data-active={windowDays === option}
                onClick={() => {
                  setWindowDays(option);
                }}
              >
                {`${String(option)} days`}
              </button>
            ))}
            {clamped && (
              <span className="stats__clamp">
                showing <Numeral>{data.window_days}</Numeral> — the ledger is not older than that
              </span>
            )}
          </div>

          {tracks.length === 0 ? (
            <p className="stats__empty">
              Nothing has begun yet. Once a track starts, its days appear here.
            </p>
          ) : (
            <div className="stats__scroll">
              <table className="table stats__grid">
                <caption className="sr-only">
                  Each cell is one day: red opened the gap, green closed it, blank held it.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Track</th>
                    <th scope="col" colSpan={data.days.length} className="stats__days">
                      <span className="stats__span">
                        <span>{data.days[0]}</span>
                        {data.days.length > 1 && <span>{data.days[data.days.length - 1]}</span>}
                      </span>
                    </th>
                    <th scope="col">Over the window</th>
                  </tr>
                </thead>
                <tbody>
                  {tracks.map((track) => (
                    <tr key={track.track_id}>
                      <th scope="row">
                        <HebrewText>{track.name_he}</HebrewText>
                        <span className="gloss">{track.name_en}</span>
                      </th>
                      {cells(data.days, track.net).map(({ day, net }) => (
                        <td
                          key={day}
                          className="stats__cell"
                          data-state={cellState(net)}
                          title={`${day}: ${net === 0 ? "held" : `${net > 0 ? "+" : ""}${String(net)}`}`}
                        >
                          <span className="sr-only">{net === 0 ? "held" : String(net)}</span>
                        </td>
                      ))}
                      <td className="stats__movement">
                        {movement(track)}
                        {track.learned_units > 0 && (
                          <span className="stats__learned">
                            {" · "}
                            <Numeral>{track.learned_units}</Numeral>{" "}
                            {track.learned_units === 1 ? track.unit_singular : track.unit_plural} on{" "}
                            <Numeral>{track.days_learned}</Numeral>{" "}
                            {track.days_learned === 1 ? "day" : "days"}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
