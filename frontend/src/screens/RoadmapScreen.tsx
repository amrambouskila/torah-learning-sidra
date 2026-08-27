import { useEffect, useState, type ReactElement } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import { Numeral } from "@/components/Numeral";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { loadRoadmap } from "@/stores/roadmapSlice";
import type { RoadmapRow } from "@/types/RoadmapRow";

type SortKey = "finish" | "remaining";

function compare(key: SortKey) {
  return (left: RoadmapRow, right: RoadmapRow): number => {
    if (key === "remaining") return right.units_remaining - left.units_remaining;
    // A track with no projection has no date to sort by, so it goes last rather than first.
    if (left.projected_finish === null) return 1;
    if (right.projected_finish === null) return -1;
    return left.projected_finish.localeCompare(right.projected_finish);
  };
}

export function RoadmapScreen(): ReactElement {
  const dispatch = useAppDispatch();
  const { data, status, error, isConflict } = useAppSelector((state) => state.roadmap);
  const [sort, setSort] = useState<SortKey>("finish");

  useEffect(() => {
    void dispatch(loadRoadmap(undefined));
  }, [dispatch]);

  if (status === "failed" && error !== null) {
    return (
      <section className="screen">
        <h1 className="screen__title">Roadmap</h1>
        <ErrorBanner message={error} isConflict={isConflict} />
      </section>
    );
  }

  return (
    <section className="screen">
      <h1 className="screen__title">Roadmap</h1>
      <p className="screen__lede">
        With a fixed rate and a complete catalog, a finish date is arithmetic rather than a guess.
        Every day of debt slides the date by exactly one day.
      </p>

      <div className="roadmap__sort">
        <span className="eyebrow">Sort</span>
        {(["finish", "remaining"] as const).map((key) => (
          <button
            key={key}
            type="button"
            className="pill pill--button"
            data-active={sort === key}
            onClick={() => {
              setSort(key);
            }}
          >
            {key === "finish" ? "Finish date" : "Remaining"}
          </button>
        ))}
      </div>

      <div className="scroll-x">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Track</th>
              <th scope="col">Done</th>
              <th scope="col">Remaining</th>
              <th scope="col">Per day</th>
              <th scope="col">Debt</th>
              <th scope="col">Finishes</th>
              <th scope="col">A year would need</th>
            </tr>
          </thead>
          <tbody>
            {[...data].sort(compare(sort)).map((row) => (
              <tr key={row.track_id}>
                <th scope="row">
                  <HebrewText>{row.name_he}</HebrewText>
                  <LatinGloss>
                    {row.work_ref_title === null || row.work_ref_title === row.name_en
                      ? row.name_en
                      : `${row.name_en} · ${row.work_ref_title}`}
                  </LatinGloss>
                  {row.corpus_en !== null && row.corpus_years !== null && (
                    <span className="road__wider">
                      all of {row.corpus_en} at this pace: <Numeral>{row.corpus_years.toFixed(1)}</Numeral> years
                    </span>
                  )}
                </th>
                <td>
                  <Numeral>{`${String(row.actual_ordinal)} / ${String(row.total)}`}</Numeral>
                </td>
                <td>
                  <Numeral>{row.units_remaining}</Numeral>
                </td>
                <td>
                  <Numeral>{row.rate_per_day.toFixed(2)}</Numeral>
                </td>
                <td>{row.debt === 0 ? <span className="muted">—</span> : <Numeral>{row.debt}</Numeral>}</td>
                <td>
                  {row.projected_finish === null ? (
                    <span className="muted">no schedule</span>
                  ) : (
                    <Numeral>{row.projected_finish}</Numeral>
                  )}
                </td>
                <td>
                  <Numeral>{`${row.yearly_cycle_rate.toFixed(2)}/day`}</Numeral>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
