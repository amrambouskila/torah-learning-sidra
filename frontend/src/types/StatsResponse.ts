export interface StatsTrack {
  readonly track_id: string;
  readonly name_en: string;
  readonly name_he: string;
  readonly unit_singular: string;
  readonly unit_plural: string;
  /** Null on a chavrusa track, which carries staleness rather than debt. */
  readonly debt_now: number | null;
  /** Where the debt stood when the window opened, so the direction of travel is visible. */
  readonly debt_then: number | null;
  readonly learned_units: number;
  readonly days_learned: number;
  readonly last_learned_on: string | null;
  /** First real advance. Null means never opened, which is not the same as opened and idle. */
  readonly opened_on: string | null;
  /** Billed minus learned, one per day. Positive opened the gap, negative closed it. */
  readonly net: readonly number[];
}

export interface StatsStanding {
  readonly behind: number;
  readonly on_pace: number;
  readonly ahead: number;
  readonly not_started: number;
  readonly chavrusa: number;
}

export interface StatsResponse {
  readonly on: string;
  readonly days: readonly string[];
  readonly window_days: number;
  /** What was asked for. The window is clamped to the ledger's own age. */
  readonly requested_window_days: number;
  readonly standing: StatsStanding;
  readonly streak: { readonly current: number; readonly longest: number };
  readonly tracks: readonly StatsTrack[];
}
