/**
 * Where one unit stands relative to the two markers.
 *
 * `between` is the debt made visible: units the schedule has passed but the learning has not.
 */
export type RailState = "done" | "actual" | "between" | "scheduled" | "ahead";
