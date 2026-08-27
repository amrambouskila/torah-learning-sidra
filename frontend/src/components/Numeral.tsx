import type { ReactElement } from "react";

interface NumeralProps {
  readonly children: string | number;
  readonly className?: string;
  readonly title?: string;
}

/**
 * Every countable value in the app: ordinals, debts, percentages, dates.
 *
 * Tabular figures are what let a column of debts line up; proportional digits make a table of
 * numbers look ragged even when the numbers are right.
 */
export function Numeral({ children, className, title }: NumeralProps): ReactElement {
  return (
    <span className={className === undefined ? "num" : `num ${className}`} dir="ltr" title={title}>
      {children}
    </span>
  );
}
