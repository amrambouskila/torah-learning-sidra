import type { ReactElement } from "react";

import { Numeral } from "@/components/Numeral";
import type { TrackRow } from "@/types/TrackRow";
import { debtPhrase } from "@/utils/debtPhrase";

interface DebtBadgeProps {
  readonly track: TrackRow;
}

/**
 * What the track owes, in words.
 *
 * A surplus reads as "3 days ahead" rather than as a negative debt: a minus sign in front of a
 * number you earned reads as a penalty, and banking credit is the opposite of that.
 */
export function DebtBadge({ track }: DebtBadgeProps): ReactElement {
  const { tone, value, suffix } = debtPhrase(track);
  return (
    <span className="debt" data-tone={tone}>
      <Numeral className="debt__value">{value}</Numeral>
      <span className="debt__suffix">{suffix}</span>
    </span>
  );
}
