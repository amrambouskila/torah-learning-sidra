import type { ReactElement } from "react";

interface TagPillProps {
  readonly name: string;
  readonly color?: string | null;
  readonly onClick?: () => void;
  readonly active?: boolean;
}

/** A tag as it appears on a row or in a filter. A pure label: it carries no cadence or rule. */
export function TagPill({ name, color, onClick, active = false }: TagPillProps): ReactElement {
  const style = color === null || color === undefined ? undefined : { borderColor: color, color };
  if (onClick === undefined) {
    return (
      <span className="pill" style={style}>
        {name}
      </span>
    );
  }
  return (
    <button type="button" className="pill pill--button" data-active={active} style={style} onClick={onClick}>
      {name}
    </button>
  );
}
