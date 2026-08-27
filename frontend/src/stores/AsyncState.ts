/** What every fetched resource in the app looks like while it is arriving. */
export interface AsyncState<T> {
  readonly data: T;
  readonly status: "idle" | "loading" | "ready" | "failed";
  /** The backend's own sentence, kept so a 409 about the calendar reaches the screen intact. */
  readonly error: string | null;
  /** True when the failure was a 409: the data is not ready, not that the request was wrong. */
  readonly isConflict: boolean;
}

export function initialAsyncState<T>(data: T): AsyncState<T> {
  return { data, status: "idle", error: null, isConflict: false };
}
