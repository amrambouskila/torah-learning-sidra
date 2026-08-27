import type { TrackRow } from "./TrackRow";

export interface TodayResponse {
  readonly civil_date: string;
  readonly hebrew_date: string;
  readonly parsha_en: readonly string[];
  readonly parsha_he: readonly string[];
  readonly is_yom_tov: boolean;
  readonly daily: readonly TrackRow[];
  readonly shabbat: readonly TrackRow[];
  readonly chavrusa: readonly TrackRow[];
}
