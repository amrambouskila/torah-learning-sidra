import { useEffect, useState, type ReactElement } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import { Numeral } from "@/components/Numeral";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { loadSequence } from "@/stores/sequenceSlice";
import { loadTracks } from "@/stores/tracksSlice";
import type { SequenceStage } from "@/types/SequenceResponse";
import type { TrackRow } from "@/types/TrackRow";

/** The codes Ein Mishpat maps. A Gemara or Chumash track has no apparatus to sequence. */
const CODES = new Set(["Mishneh Torah", "Shulchan Arukh"]);

function codeTracks(tracks: readonly TrackRow[]): readonly TrackRow[] {
  return tracks.filter((track) => CODES.has(track.at?.work_ref_title.split(",")[0] ?? ""));
}

/** The track standing in this masechta right now, if one is. */
function learningIt(tracks: readonly TrackRow[], masechta: string | null): TrackRow | undefined {
  if (masechta === null) return undefined;
  return tracks.find((track) => track.at?.work_ref_title === masechta);
}

function stageLabel(stage: SequenceStage): string {
  return stage.masechta_en ?? "no masechta of its own";
}

/**
 * Which masechta the code asks for next.
 *
 * Amram's Gemara follows his Rambam rather than Shas order: whatever hilchos he is up to, the
 * Gemara is the masechta that section draws on. When the Rambam crosses a section no masechta
 * owns — Teshuvah, Deos, Talmud Torah — the Gemara does not move; he stays where he is until a
 * section with a real masechta arrives. Every pairing here is Ein Mishpat's, and the evidence
 * behind each travels with it so a close call stays visible rather than reading as a fact.
 */
export function SequenceScreen(): ReactElement {
  const dispatch = useAppDispatch();
  const tracks = useAppSelector((state) => state.tracks.data);
  const { data, status, error, isConflict } = useAppSelector((state) => state.sequence);
  const [trackId, setTrackId] = useState("");

  useEffect(() => {
    void dispatch(loadTracks(undefined));
  }, [dispatch]);

  const codes = codeTracks(tracks);
  const chosen = trackId === "" ? (codes[0]?.id ?? "") : trackId;

  useEffect(() => {
    if (chosen !== "") void dispatch(loadSequence(chosen));
  }, [dispatch, chosen]);

  return (
    <section className="screen">
      <h1 className="screen__title">Sequence</h1>
      <p className="screen__lede">
        Which Gemara the code asks for next. Whatever hilchos you are up to, the masechta is the
        one that section draws on — and where a section has no masechta of its own, the Gemara does
        not move: you stay where you are until one that does comes round.
      </p>
      <p className="align__scope">
        Every pairing is Ein Mishpat&apos;s, not a curriculum invented here. A section counts as
        having a masechta only when one holds a quarter of its citations and leads the runner-up by
        half again — which is why Teshuvah, Deos and Talmud Torah name none.
      </p>

      {status === "failed" && error !== null && <ErrorBanner message={error} isConflict={isConflict} />}

      {codes.length === 0 ? (
        <p className="align__empty">
          Nothing to sequence yet. Open a Rambam or Shulchan Aruch track, record where you are, and
          the masechtos it asks for appear here.
        </p>
      ) : (
        <label className="align__picker">
          <span className="eyebrow">Following</span>
          <select
            value={chosen}
            onChange={(event) => {
              setTrackId(event.target.value);
            }}
          >
            {codes.map((track) => (
              <option key={track.id} value={track.id}>
                {track.name_en}
              </option>
            ))}
          </select>
        </label>
      )}

      {data !== null && data.at !== null && (
        <p className="seq__at">
          Up to <LatinGloss>{data.at.ref}</LatinGloss>
        </p>
      )}

      {data !== null && data.stages.length === 0 && status === "ready" && (
        <p className="align__empty">Nothing ahead — this code is finished.</p>
      )}

      <ol className="seq">
        {data?.stages.map((stage) => (
          <li
            key={`${stage.masechta_en ?? "none"}-${stage.halachos_until}`}
            className="seq__stage"
            data-current={stage.is_current}
          >
            <div className="seq__head">
              {stage.masechta_he !== null && <HebrewText size="headline">{stage.masechta_he}</HebrewText>}
              <LatinGloss>{stageLabel(stage)}</LatinGloss>
              {stage.is_current ? (
                <span className="pill seq__now">learning now</span>
              ) : (
                <span className="seq__when">
                  in <Numeral>{stage.halachos_until}</Numeral> halachos
                </span>
              )}
              {stage.seen_before && <span className="pill seq__again">already been here</span>}
            </div>

            <p className="seq__books">
              {stage.works.map((work) => work.ref_title.replace(/^Mishneh Torah, |^Shulchan Arukh, /, "")).join(" · ")}
              {" — "}
              <Numeral>{stage.halachos_in_stage}</Numeral> halachos
            </p>

            {stage.share !== null && stage.links !== null && (
              <p className="seq__evidence">
                <Numeral>{Math.round(stage.share * 100)}</Numeral>% of its citations —{" "}
                <Numeral>{stage.links}</Numeral> of them
                {stage.runner_up !== null && <> · next closest {stage.runner_up}</>}
              </p>
            )}

            {stage.is_current && (
              <SeqPace
                runway={data.stages[1]?.halachos_until ?? stage.halachos_in_stage}
                learning={learningIt(tracks, stage.masechta_en)}
              />
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

interface SeqPaceProps {
  /** Halachos left before the code moves on — the next stage's distance, not this stage's length,
   * because he is already partway through the one he is in. */
  readonly runway: number;
  readonly learning: TrackRow | undefined;
}

/**
 * What finishing on time would take.
 *
 * Expressed as a ratio rather than a date, because the code is learned with a chavrusa and a
 * chavrusa has no rate — asking when they will arrive would be inventing a number.
 */
function SeqPace({ runway, learning }: SeqPaceProps): ReactElement | null {
  if (learning === undefined) return null;
  const left = Math.max(0, learning.total - learning.actual_ordinal);
  if (left === 0 || runway <= 0) return null;

  return (
    <p className="seq__pace">
      <LatinGloss>{learning.name_en}</LatinGloss> has <Numeral>{left}</Numeral> {learning.unit_plural}{" "}
      left and <Numeral>{runway}</Numeral> halachos of runway — one {learning.unit_singular} for
      every <Numeral>{(runway / left).toFixed(1)}</Numeral> halachos.
    </p>
  );
}
