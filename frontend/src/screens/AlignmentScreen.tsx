import { useEffect, useState, type ReactElement } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import { Numeral } from "@/components/Numeral";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { loadAlignment } from "@/stores/alignmentSlice";
import { loadTracks } from "@/stores/tracksSlice";

/** The works Ein Mishpat covers, by the first segment of their ref_title. */
const ALIGNABLE = new Set(["Mishneh Torah", "Shulchan Arukh"]);

/**
 * Which masechtos sit behind the hilchos a track is currently in.
 *
 * Presented as a distribution rather than one recommendation, because that is what the apparatus
 * supports: Krias Shema is 71% Berakhot, which is unambiguous, while Teshuva's best match is 18%
 * across a long tail. Showing both the same way would misrepresent how sure the map is.
 */
export function AlignmentScreen(): ReactElement {
  const dispatch = useAppDispatch();
  const tracks = useAppSelector((state) => state.tracks.data);
  const { data, status, error, isConflict } = useAppSelector((state) => state.alignment);
  const [trackId, setTrackId] = useState("");

  useEffect(() => {
    void dispatch(loadTracks(undefined));
  }, [dispatch]);

  // Ein Mishpat maps the codes to their Talmudic sources, so only a track standing in a halachic
  // work can be asked. Offering the other seventeen and answering each with a blank screen is
  // what made this look broken.
  const askable = tracks.filter((track) => ALIGNABLE.has(track.at?.work_ref_title.split(",")[0] ?? ""));
  const chosen = trackId === "" ? (askable[0]?.id ?? "") : trackId;

  useEffect(() => {
    if (chosen !== "") void dispatch(loadAlignment(chosen));
  }, [dispatch, chosen]);

  return (
    <section className="screen">
      <h1 className="screen__title">Alignment</h1>
      <p className="screen__lede">
        Which Gemara sits behind the halacha you are learning. Ein Mishpat Ner Mitzvah is the
        marginal apparatus that cites, for each ruling in the Rambam and the Shulchan Aruch, the
        daf it comes from — so a hilchos book can be ranked by where its sources actually are.
        This is a distribution, not a recommendation: Hilchos Avoda Zara is 42% Avodah Zarah and
        27% Sanhedrin, and saying only &ldquo;Avodah Zarah&rdquo; would hide the second half.
      </p>
      <p className="align__scope">
        Only the halachic tracks can be asked — the Rambam and the Shulchan Aruch. A Chumash or a
        Gemara track has no Ein Mishpat to read, so it is not offered here.
      </p>

      <label className="align__picker">
        <span className="eyebrow">Track</span>
        <select
          value={chosen}
          onChange={(event) => {
            setTrackId(event.target.value);
          }}
        >
          {askable.map((track) => (
            <option key={track.id} value={track.id}>
              {track.name_en}
            </option>
          ))}
        </select>
      </label>

      {status === "failed" && error !== null && <ErrorBanner message={error} isConflict={isConflict} />}

      {askable.length === 0 && (
        <p className="align__empty">
          Nothing to align yet. Open a Rambam or Shulchan Aruch track, record where you are, and
          the masechtos behind it appear here.
        </p>
      )}

      {chosen !== "" && status === "ready" && data.length === 0 && (
        <p className="align__empty">
          No Ein Mishpat edges reach the work this track currently stands in. That is an honest
          empty, not a failure: the apparatus does not cover everything.
        </p>
      )}

      {data.length > 0 && (
        <>
          <ol className="align">
            {data.map((row) => (
              <li key={row.masechta} className="align__row" data-inferred={row.is_inferred}>
                <span className="align__name">
                  <LatinGloss>{row.masechta}</LatinGloss>
                </span>
                <span className="align__bar">
                  <i className="align__fill" style={{ width: `${String(Math.round(row.share * 100))}%` }} />
                </span>
                <Numeral className="align__share">{`${String(Math.round(row.share * 100))}%`}</Numeral>
                <Numeral className="align__links">{row.links}</Numeral>
                {row.is_inferred && <span className="align__mark">inferred</span>}
              </li>
            ))}
          </ol>
          <p className="align__legend">
            <span className="align__mark">inferred</span> means every edge behind that row is
            bridged through Tur&apos;s siman numbering rather than cited directly by Ein Mishpat.
          </p>
          <HebrewText className="align__he">עין משפט נר מצוה</HebrewText>
        </>
      )}
    </section>
  );
}
