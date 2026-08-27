import type { ReactElement } from "react";

import type { RailState } from "@/types/RailState";
import type { RailUnit } from "@/types/RailUnit";

interface RailNodeProps {
  readonly unit: RailUnit;
  readonly state: RailState;
  readonly onSelect: (ordinal: number) => void;
}

const DESCRIPTION: Record<RailState, string> = {
  done: "learned",
  actual: "where you are",
  between: "owed",
  scheduled: "where the schedule is",
  ahead: "ahead",
};

/**
 * The node on the rail *is* the control, as it is in the sibling TV app: marking your place and
 * seeing how far along you are are the same gesture rather than two.
 */
export function RailNode({ unit, state, onSelect }: RailNodeProps): ReactElement {
  return (
    <button
      type="button"
      className="rail-node"
      data-state={state}
      aria-label={`${unit.label_en}: ${DESCRIPTION[state]}. Set your position here.`}
      onClick={() => {
        onSelect(unit.ordinal);
      }}
    />
  );
}
