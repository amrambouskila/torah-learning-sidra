import { useRef, useState, type ReactElement, type UIEvent } from "react";

import { HebrewText } from "@/components/HebrewText";
import { Numeral } from "@/components/Numeral";
import { RailNode } from "@/components/RailNode";
import { ROW_HEIGHT, useRailWindow } from "@/hooks/useRailWindow";
import { SefariaLink } from "@/components/SefariaLink";
import { railState } from "@/utils/railState";

interface RailProps {
  readonly trackId: string;
  readonly total: number;
  readonly actual: number;
  readonly scheduled: number | null;
  readonly height?: number;
  readonly onSelect: (ordinal: number) => void;
}

const DEFAULT_HEIGHT = 560;

/**
 * The full spine, windowed.
 *
 * Two markers on one line: the segment lit to the actual position, a ghost at the scheduled one.
 * The gap between them is not a statistic about the debt — it *is* the debt, rendered.
 */
export function Rail({
  trackId,
  total,
  actual,
  scheduled,
  height = DEFAULT_HEIGHT,
  onSelect,
}: RailProps): ReactElement {
  const [scrollTop, setScrollTop] = useState(0);
  const viewport = useRef(height);
  const { first, units, error } = useRailWindow(trackId, total, scrollTop, viewport.current);

  const onScroll = (event: UIEvent<HTMLDivElement>): void => {
    setScrollTop(event.currentTarget.scrollTop);
  };

  return (
    <div className="rail" style={{ height }} onScroll={onScroll} data-testid="rail-viewport">
      <div className="rail__runway" style={{ height: total * ROW_HEIGHT }}>
        {error !== null && <p className="rail__error">{error}</p>}
        <ol className="rail__list" style={{ transform: `translateY(${String((first - 1) * ROW_HEIGHT)}px)` }}>
          {units.map((unit) => {
            const state = railState(unit.ordinal, actual, scheduled);
            return (
              <li key={unit.ordinal} className="rail__row" data-state={state} style={{ height: ROW_HEIGHT }}>
                <RailNode unit={unit} state={state} onSelect={onSelect} />
                <Numeral className="rail__ordinal">{unit.ordinal}</Numeral>
                <HebrewText className="rail__he">{unit.label_he}</HebrewText>
                <SefariaLink url={unit.sefaria_url} label={unit.ref} />
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
