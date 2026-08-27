import type { Category } from "./Category";
import type { Period } from "./Period";
import type { PositionModel } from "./PositionModel";
import type { TrackKind } from "./TrackKind";

export interface TrackRow {
  readonly id: string;
  readonly name_en: string;
  readonly name_he: string;
  readonly category: Category;
  readonly kind: TrackKind;
  readonly period: Period;
  readonly rate: number;
  readonly total: number;
  /** Set when the track repeats annually. Then `actual_ordinal` passes `total` and keeps going. */
  readonly cycle_length: number | null;
  /** Which time round he is, counting from 1. Null on a track that runs once. */
  readonly cycle_index: number | null;
  /** The furthest ordinal the rail may offer and the advance endpoint will accept. */
  readonly reachable_to: number;
  readonly actual_ordinal: number;
  /** What this track's units are called, so a badge reads "20 amudim behind". */
  readonly unit_singular: string;
  readonly unit_plural: string;
  readonly at: PositionModel | null;
  readonly up_next: PositionModel | null;
  readonly scheduled_at: PositionModel | null;
  /** Null on a chavrusa track, which carries staleness rather than debt. */
  readonly debt: number | null;
  readonly days_ahead: number;
  readonly is_behind: boolean;
  readonly starts_in_days: number | null;
  /** The declared start date, ISO. `starts_in_days` only survives while it is still future. */
  readonly starts_on: string | null;
  readonly is_finished: boolean;
  readonly last_advanced_on: string | null;
  readonly days_stale: number | null;
  readonly tags: readonly string[];
  readonly chavrusa: string | null;
}
