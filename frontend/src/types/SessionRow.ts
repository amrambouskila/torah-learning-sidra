export interface SessionRow {
  readonly occurred_on: string;
  readonly hebrew_date: string;
  readonly from_ordinal: number;
  readonly to_ordinal: number;
  readonly unit_count: number;
  readonly note: string | null;
}
