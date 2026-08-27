import type { ReactElement } from "react";

interface SefariaLinkProps {
  readonly url: string | null;
  readonly label: string;
}

/**
 * A deep link where Sefaria has the text, plain text where it does not.
 *
 * Likutei Sichot and The Midrash Says are not on Sefaria at all. Showing the position without a
 * link is the normal state for them, not a degradation to apologise for.
 */
export function SefariaLink({ url, label }: SefariaLinkProps): ReactElement {
  if (url === null) return <span className="ref ref--plain">{label}</span>;
  return (
    <a className="ref" href={url} target="_blank" rel="noreferrer noopener">
      {label}
    </a>
  );
}
