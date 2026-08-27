export interface PaceRow {
  readonly row_id: string;
  readonly scope_en: string;
  readonly unit_singular: string;
  readonly unit_plural: string;
  readonly total: number;
  /** Units a day to finish inside the chosen horizon. */
  readonly per_day_for_horizon: number;
  /** How long the chosen rate would take. A duration in years, never a date. */
  readonly years_at_rate: number;
  readonly note: string | null;
}
