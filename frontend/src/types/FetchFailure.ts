/** A failed fetch, reduced to what a screen can actually show. */
export interface FetchFailure {
  readonly message: string;
  /** A 409 means the data is not ready — a missing calendar span, say — not a bad request. */
  readonly isConflict: boolean;
}
