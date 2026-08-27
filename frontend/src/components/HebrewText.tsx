import type { ReactElement } from "react";

interface HebrewTextProps {
  readonly children: string;
  /** `h1`…`h3` for headlines, `span` inside a row. Everything else is a `span`. */
  readonly as?: "span" | "h1" | "h2" | "h3";
  readonly size?: "row" | "headline" | "display";
  readonly className?: string;
}

const SIZE: Record<string, string> = {
  row: "var(--he-step-3)",
  headline: "var(--he-step-5)",
  display: "var(--he-step-6)",
};

/**
 * Hebrew is primary in this app; it never arrives hand-encoded, only verbatim from Sefaria.
 *
 * The RTL isolate is not optional: a Latin ref rendered beside a Hebrew label without it reorders
 * the line, and the result reads as corrupted text rather than as a layout bug.
 */
export function HebrewText({
  children,
  as = "span",
  size = "row",
  className,
}: HebrewTextProps): ReactElement {
  const Tag = as;
  return (
    <Tag
      className={className === undefined ? "he" : `he ${className}`}
      dir="rtl"
      lang="he"
      style={{ fontSize: SIZE[size] }}
    >
      {children}
    </Tag>
  );
}
