/** One resolved place in a track. Field names mirror the API exactly; nothing is renamed. */
export interface PositionModel {
  readonly ref: string;
  readonly label_en: string;
  readonly label_he: string;
  readonly work_ref_title: string;
  readonly work_title_he: string;
  readonly corpus_ordinal: number;
  readonly seq_in_work: number;
  /** Null for Likutei Sichot and The Midrash Says, which are not on Sefaria at all. */
  readonly sefaria_url: string | null;
}
