import type { JobState } from "./JobState";

/**
 * The one job, as the screen polls it.
 *
 * There is no id: the app holds a single slot, because every job it runs is atomic and so a job
 * lost to a restart leaves nothing half-finished to go back to.
 */
export interface JobView {
  readonly kind: string;
  readonly state: JobState;
  readonly phase: string;
  readonly done: number;
  /** Zero when the job has no natural tick; the screen shows the phase alone. */
  readonly total: number;
  readonly started_at: string;
  readonly finished_at: string | null;
  readonly detail: string;
  readonly error: string;
}
