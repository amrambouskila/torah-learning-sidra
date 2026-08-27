import { useEffect, useState, type ReactElement } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { Numeral } from "@/components/Numeral";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { loadPace } from "@/stores/paceSlice";

const HORIZONS: readonly number[] = [1, 3, 7, 18];
const RATES: readonly number[] = [1, 2, 3, 5, 10];

/**
 * What a full cycle would cost, at any rate or in any horizon.
 *
 * Deliberately not the Roadmap. Nothing here reads the ledger: there is no position, no debt and
 * no date anywhere on the screen, and the horizon is a *duration* — "14.7 years" — which cannot
 * be misread as a finish line. Several rows are not tracks at all, and two bodies appear twice at
 * different granularities, which a roadmap structurally could not do.
 */
export function PaceScreen(): ReactElement {
  const dispatch = useAppDispatch();
  const { data, status, error, isConflict } = useAppSelector((state) => state.pace);
  const [years, setYears] = useState(1);
  const [perDay, setPerDay] = useState(1);

  useEffect(() => {
    void dispatch(loadPace({ years, perDay }));
  }, [dispatch, years, perDay]);

  return (
    <section className="screen">
      <h1 className="screen__title">Pace Explorer</h1>
      <p className="screen__lede">
        None of this is your plan. These are the cycles as the catalog counts them — nothing here
        reads your ledger, and several rows are not tracks at all. Pick a horizon to see the rate
        it would take, or a rate to see how long it would run.
      </p>

      {status === "failed" && error !== null && <ErrorBanner message={error} isConflict={isConflict} />}

      <div className="pace__knobs">
        <div className="pace__knob">
          <span className="eyebrow">Finish in</span>
          <div className="pace__choices">
            {HORIZONS.map((option) => (
              <button
                key={option}
                type="button"
                className="pill pill--button"
                data-active={years === option}
                onClick={() => {
                  setYears(option);
                }}
              >
                {option === 1 ? "1 year" : `${String(option)} years`}
              </button>
            ))}
          </div>
        </div>

        <div className="pace__knob">
          <span className="eyebrow">Or learn</span>
          <div className="pace__choices">
            {RATES.map((option) => (
              <button
                key={option}
                type="button"
                className="pill pill--button"
                data-active={perDay === option}
                onClick={() => {
                  setPerDay(option);
                }}
              >
                {option === 1 ? "1 a day" : `${String(option)} a day`}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="scroll-x">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Body</th>
              <th scope="col">Unit</th>
              <th scope="col">Total</th>
              <th scope="col">
                A day, for {years === 1 ? "a year" : `${String(years)} years`}
              </th>
              <th scope="col">
                Years, at {perDay === 1 ? "1 a day" : `${String(perDay)} a day`}
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.row_id}>
                <th scope="row">{row.scope_en}</th>
                <td>{row.unit_plural}</td>
                <td>
                  <Numeral>{row.total.toLocaleString("en")}</Numeral>
                </td>
                <td>
                  <Numeral>{row.per_day_for_horizon.toFixed(2)}</Numeral>
                </td>
                <td>
                  <Numeral>{row.years_at_rate.toFixed(1)}</Numeral>
                  {row.note !== null && (
                    <span className="pace__note" title={row.note}>
                      ⃰
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.some((row) => row.note !== null) && (
        <ul className="pace__notes">
          {data
            .filter((row) => row.note !== null)
            .map((row) => (
              <li key={row.row_id}>
                <strong>
                  {row.scope_en} · {row.unit_plural}
                </strong>{" "}
                {row.note}
              </li>
            ))}
        </ul>
      )}
    </section>
  );
}
