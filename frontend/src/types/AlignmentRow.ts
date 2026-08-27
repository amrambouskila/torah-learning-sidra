export interface AlignmentRow {
  readonly masechta: string;
  readonly links: number;
  readonly share: number;
  /** True when every edge behind the row is bridged through Tur rather than directly cited. */
  readonly is_inferred: boolean;
}
