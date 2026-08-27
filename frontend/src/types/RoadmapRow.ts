export interface RoadmapRow {
  readonly track_id: string;
  readonly name_en: string;
  readonly name_he: string;
  /** The work the track is standing in. A row saying only "Gemara" overclaims by a factor of 35. */
  readonly work_ref_title: string | null;
  /** The whole body that work belongs to, when it is larger than the track. */
  readonly corpus_en: string | null;
  readonly corpus_total: number | null;
  /** How long the whole body would take at this track's rate. The honest second scale. */
  readonly corpus_years: number | null;
  readonly total: number;
  readonly actual_ordinal: number;
  readonly units_remaining: number;
  readonly rate_per_day: number;
  readonly debt: number;
  /** Null on a chavrusa track, which has no rate to project from. */
  readonly projected_finish: string | null;
  /** How many units a day a full cycle in a year would take. The Pace Explorer's number. */
  readonly yearly_cycle_rate: number;
}
