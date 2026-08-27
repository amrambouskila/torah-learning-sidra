import type { PositionModel } from "@/types/PositionModel";

export interface SequenceWork {
  readonly ref_title: string;
  readonly title_he: string;
  readonly halachos: number;
}

export interface SequenceStage {
  /** Null only while the code opens on sections no masechta owns. */
  readonly masechta_en: string | null;
  readonly masechta_he: string | null;
  readonly share: number | null;
  readonly links: number | null;
  /** The masechta that came second, so a close call is visible rather than hidden. */
  readonly runner_up: string | null;
  readonly works: readonly SequenceWork[];
  readonly halachos_in_stage: number;
  /** From where he stands now to this stage's first halachah. Zero for the stage he is in. */
  readonly halachos_until: number;
  readonly is_current: boolean;
  /** This masechta already had an earlier stage; whether to learn it again is his call. */
  readonly seen_before: boolean;
}

export interface SequenceResponse {
  readonly track_id: string;
  readonly name_en: string;
  readonly name_he: string;
  readonly at: PositionModel | null;
  readonly stages: readonly SequenceStage[];
}
