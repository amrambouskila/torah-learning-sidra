import { useEffect, useMemo, useState, type FormEvent, type ReactElement } from "react";

import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import { api } from "@/api/endpoints";
import type { AdvanceDestination } from "@/types/AdvanceDestination";
import type { RailUnit } from "@/types/RailUnit";
import type { TrackRow } from "@/types/TrackRow";
import { correctionPhrase } from "@/utils/correctionPhrase";

interface AdvanceDialogProps {
  readonly track: TrackRow;
  readonly onConfirm: (destination: AdvanceDestination, label: string, note: string | undefined) => void;
  readonly onCancel: () => void;
}

/**
 * How far ahead the list reaches. Far past any single sitting — he can learn thirty halachos in a
 * night — and comfortably inside the rail endpoint's 500-unit span. Anything beyond it is typed.
 */
const AHEAD = 200;

/**
 * How far back it reaches. Far enough for any correction he would make by eye, and short enough
 * that the ordinary case — the next unit — is still what the dialog opens on.
 */
const BEHIND = 20;

/**
 * Written as escapes rather than as the characters themselves.
 *
 * A bare directional mark in a source file is indistinguishable from a trojan-source attack --
 * a scanner is right to flag one, and a reviewer cannot see it at all. Spelled this way the
 * file contains no bidi characters, so there is nothing to suppress and nothing hidden.
 */
const RIGHT_TO_LEFT_ISOLATE = "\u2067";
const POP_DIRECTIONAL_ISOLATE = "\u2069";

/** Either a unit he picked off the list, or a reference he typed. */
type Choice = { readonly unit: RailUnit } | { readonly text: string };

/**
 * How an option names its unit.
 *
 * Usually the address, because that is what he says out loud — `5:9`, `38b`. An aliyah is the
 * exception: its label is "Chamishi" in every parsha there is, so the ref is what locates it.
 */
/**
 * A Hebrew label wrapped so it cannot reorder the Latin around it.
 *
 * U+2067 RIGHT-TO-LEFT ISOLATE and U+2069 POP DIRECTIONAL ISOLATE. A closed `<select>` renders one
 * line of plain text, so without the isolate the bidi algorithm pulls the address and the em dash
 * around the Hebrew and the option reads in the wrong order. Named here rather than inlined
 * because bare directional characters in a source file are indistinguishable from a trojan-source
 * attack, and a scanner is right to flag them.
 */
function isolated(hebrew: string): string {
  return `${RIGHT_TO_LEFT_ISOLATE}${hebrew}${POP_DIRECTIONAL_ISOLATE}`;
}

function address(unit: RailUnit): string {
  return unit.ref.endsWith(unit.label_en) ? unit.label_en : unit.ref;
}

/**
 * Consecutive runs of units sharing a sefer, in rail order, split at the position he stands on.
 *
 * The split is what keeps the two directions from reading alike: everything at or below where he
 * is would otherwise sit in the same group as what lies ahead, and picking one of them means
 * something entirely different.
 */
function bySefer(
  units: readonly RailUnit[],
  actual: number,
): readonly {
  readonly title: string;
  readonly isBehind: boolean;
  readonly from: number;
  readonly units: RailUnit[];
}[] {
  const groups: { title: string; isBehind: boolean; from: number; units: RailUnit[] }[] = [];
  for (const unit of units) {
    const title = unit.work_title_en;
    const isBehind = unit.ordinal <= actual;
    const open = groups.at(-1);
    if (open !== undefined && open.title === title && open.isBehind === isBehind) open.units.push(unit);
    else groups.push({ title, isBehind, from: unit.ordinal, units: [unit] });
  }
  return groups;
}

/**
 * Records where Amram got to — or, going the other way, where he really is.
 *
 * He knows he finished Human Dispositions 5:7. He does not know, and should never need to work
 * out, that this was three halachos or that 5:7 is unit 289 of the corpus — so this dialog never
 * shows an ordinal. It offers the units around him by their real addresses, and he picks the one
 * he stopped at.
 *
 * A picked unit travels as its ordinal rather than its address, because the address alone is
 * ambiguous across books: three of the options below read `5:9`, and a ref would resolve to the
 * first of them. What he typed himself travels as a ref, which is the whole point of that field.
 */
export function AdvanceDialog({ track, onConfirm, onCancel }: AdvanceDialogProps): ReactElement {
  const [span, setSpan] = useState<readonly RailUnit[]>([]);
  const [choice, setChoice] = useState<Choice | null>(null);
  const [note, setNote] = useState("");

  const nextOrdinal = track.actual_ordinal + 1;
  const first = Math.max(1, track.actual_ordinal - BEHIND);
  const scheduled = track.scheduled_at?.corpus_ordinal ?? null;

  useEffect(() => {
    const last = Math.min(track.reachable_to, Math.max(nextOrdinal + AHEAD - 1, scheduled ?? 0));
    api
      .rail(track.id, first, last)
      .then((units) => {
        setSpan(units);
        return units;
      })
      .catch(() => {
        // The list is a convenience; the field below still takes a reference typed by hand.
        setSpan([]);
      });
  }, [track.id, first, nextOrdinal, scheduled, track.reachable_to]);

  const sefarim = useMemo(() => bySefer(span, track.actual_ordinal), [span, track.actual_ordinal]);

  // Untouched, the dialog stands at the next unit — the ordinary day — even though the list now
  // opens twenty units behind it. Once he says otherwise, his word holds even if the list arrives
  // afterwards.
  const next = span.find((unit) => unit.ordinal === nextOrdinal);
  const chosen: Choice = choice ?? (next === undefined ? { text: "" } : { unit: next });
  const label = "unit" in chosen ? address(chosen.unit) : chosen.text;

  const isCorrection = "unit" in chosen && chosen.unit.ordinal < track.actual_ordinal;

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    const destination: AdvanceDestination =
      "unit" in chosen ? { toOrdinal: chosen.unit.ordinal } : { toRef: chosen.text.trim() };
    onConfirm(destination, label.trim(), note.trim() === "" ? undefined : note.trim());
  };

  const catchUp = span.find((unit) => unit.ordinal === scheduled);

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label={`Advance ${track.name_en}`}>
      <form className="dialog" onSubmit={submit}>
        <header className="dialog__head">
          <HebrewText as="h2" size="headline">
            {track.name_he}
          </HebrewText>
          <LatinGloss>{track.at === null ? track.name_en : `now at ${track.at.ref}`}</LatinGloss>
        </header>

        {span.length > 0 && (
          <label className="dialog__field advance__picker">
            <span className="eyebrow">Where did you get to?</span>
            <select
              value={"unit" in chosen ? String(chosen.unit.ordinal) : ""}
              onChange={(event) => {
                const unit = span.find((candidate) => String(candidate.ordinal) === event.target.value);
                if (unit !== undefined) setChoice({ unit });
              }}
            >
              {"text" in chosen && <option value="">Somewhere further on</option>}
              {sefarim.map((sefer) => (
                <optgroup
                  key={`${sefer.isBehind ? "behind" : "ahead"}-${sefer.title}-${String(sefer.from)}`}
                  label={sefer.isBehind ? `Behind — ${sefer.title}` : sefer.title}
                >
                  {sefer.units.map((unit) => (
                    <option key={unit.ordinal} value={String(unit.ordinal)}>
                      {unit.ordinal === scheduled
                        ? `${address(unit)} · ${isolated(unit.label_he)} — scheduled`
                        : `${address(unit)} · ${isolated(unit.label_he)}`}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
        )}

        {"unit" in chosen && (
          // A closed select shows only the address, and the address repeats across sefarim. A
          // correction can undo an advance, but only deliberately and only backwards, so what is
          // about to be recorded is still spelled out in full.
          <p className="dialog__note">
            {isCorrection ? `Correcting to ${chosen.unit.ref}` : `Recording ${chosen.unit.ref}`}
          </p>
        )}

        {isCorrection && (
          <p className="dialog__warning">
            {correctionPhrase(track, track.actual_ordinal, chosen.unit.ordinal)}
          </p>
        )}

        <label className="dialog__field">
          <span className="eyebrow">Or type where you stopped</span>
          <input
            value={label}
            placeholder={track.at?.label_en ?? ""}
            onChange={(event) => {
              setChoice({ text: event.target.value });
            }}
          />
        </label>

        {catchUp !== undefined && (
          <button
            type="button"
            className="dialog__catchup"
            onClick={() => {
              setChoice({ unit: catchUp });
            }}
          >
            Catch up to the schedule ({catchUp.label_en})
          </button>
        )}

        <label className="dialog__field">
          <span className="eyebrow">Note (optional)</span>
          <textarea
            rows={3}
            value={note}
            onChange={(event) => {
              setNote(event.target.value);
            }}
          />
        </label>

        <footer className="dialog__actions">
          <button type="button" className="dialog__cancel" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="dialog__confirm" disabled={label.trim() === ""}>
            {isCorrection ? "Correct position" : "Record"}
          </button>
        </footer>
      </form>
    </div>
  );
}
