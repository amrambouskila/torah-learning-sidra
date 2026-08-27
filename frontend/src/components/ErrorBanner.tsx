import type { ReactElement } from "react";

interface ErrorBannerProps {
  readonly message: string;
  readonly isConflict: boolean;
}

/**
 * A failure the user can act on.
 *
 * The backend's 409 for a missing calendar span names the command to run; showing "something went
 * wrong" instead would throw away the only part worth reading.
 */
export function ErrorBanner({ message, isConflict }: ErrorBannerProps): ReactElement {
  return (
    <div className="banner" data-tone={isConflict ? "waiting" : "failure"} role="alert">
      <p className="banner__title">{isConflict ? "The data is not ready yet" : "That did not work"}</p>
      <p className="banner__detail">{message}</p>
    </div>
  );
}
