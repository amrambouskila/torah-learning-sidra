import type { AdvanceDestination } from "./AdvanceDestination";

/**
 * Which operand of the schedule was wrong.
 *
 * The day it began counting, or the place it should have reached by now. They agree about today
 * and disagree about every day before it, so the caller says which rather than the server guessing.
 */
export type ScheduleCorrection = { readonly startedOn: string } | AdvanceDestination;
