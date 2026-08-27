import { useEffect, type ReactElement } from "react";

import { DebtBadge } from "@/components/DebtBadge";
import { ErrorBanner } from "@/components/ErrorBanner";
import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import { Numeral } from "@/components/Numeral";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { loadChavrusas } from "@/stores/chavrusasSlice";
import { stalenessPhrase } from "@/utils/stalenessPhrase";

export function ChavrusasScreen(): ReactElement {
  const dispatch = useAppDispatch();
  const { data, status, error, isConflict } = useAppSelector((state) => state.chavrusas);

  useEffect(() => {
    void dispatch(loadChavrusas(undefined));
  }, [dispatch]);

  if (status === "failed" && error !== null) {
    return (
      <section className="screen">
        <h1 className="screen__title">Chavrusas</h1>
        <ErrorBanner message={error} isConflict={isConflict} />
      </section>
    );
  }

  return (
    <section className="screen" data-category="chavrusa">
      <h1 className="screen__title">Chavrusas</h1>
      <p className="screen__lede">
        A chavrusa track moves when you meet, so it carries no debt. The only question worth asking
        is how long it has been — longest first.
      </p>

      {data.map((person) => (
        <article key={person.id} className="person">
          <header className="person__head">
            <h2 className="person__name">{person.name}</h2>
            <span className="person__stale" data-never={person.days_stale === null}>
              {stalenessPhrase(person.days_stale)}
            </span>
          </header>

          {person.notes !== null && <p className="person__notes">{person.notes}</p>}

          <ul className="person__tracks">
            {person.tracks.map((track) => (
              <li key={track.id} className="person__track">
                <HebrewText>{track.name_he}</HebrewText>
                <LatinGloss>{track.at?.ref ?? track.name_en}</LatinGloss>
                <DebtBadge track={track} />
              </li>
            ))}
          </ul>

          {person.sessions.length === 0 ? (
            <p className="person__empty">No sessions recorded yet.</p>
          ) : (
            <ol className="log">
              {person.sessions.map((session) => (
                <li key={`${session.occurred_on}-${String(session.to_ordinal)}`} className="log__row">
                  <Numeral className="log__date">{session.occurred_on}</Numeral>
                  <HebrewText className="log__he">{session.hebrew_date}</HebrewText>
                  <Numeral className="log__span">
                    {`${String(session.from_ordinal)} to ${String(session.to_ordinal)}`}
                  </Numeral>
                  {session.note !== null && <span className="log__note">{session.note}</span>}
                </li>
              ))}
            </ol>
          )}
        </article>
      ))}
    </section>
  );
}
