import type { ReactElement } from "react";

interface LatinGlossProps {
  readonly children: string;
  readonly className?: string;
}

/** The transliteration that sits beneath the Hebrew, never beside it and never instead of it. */
export function LatinGloss({ children, className }: LatinGlossProps): ReactElement {
  return (
    <span className={className === undefined ? "gloss" : `gloss ${className}`} dir="ltr" lang="en">
      {children}
    </span>
  );
}
