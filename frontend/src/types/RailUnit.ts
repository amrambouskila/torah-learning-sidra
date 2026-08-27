export interface RailUnit {
  readonly ordinal: number;
  readonly ref: string;
  /** The sefer the unit sits in. A track spanning books repeats its addresses in each of them. */
  readonly work_title_en: string;
  readonly work_title_he: string;
  readonly label_en: string;
  readonly label_he: string;
  readonly sefaria_url: string | null;
  readonly is_actual: boolean;
  readonly is_scheduled: boolean;
}
