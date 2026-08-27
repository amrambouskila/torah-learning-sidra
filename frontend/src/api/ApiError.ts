/**
 * An API failure carrying the backend's own sentence.
 *
 * The backend answers a missing calendar span with a 409 and a `detail` telling you which command
 * to run. Swallowing that into "request failed" would throw away the only useful part.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  /** A 409 means the data is not ready, not that the request was wrong. */
  get isConflict(): boolean {
    return this.status === 409;
  }
}
