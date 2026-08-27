import type { ReactElement } from "react";

import type { JobView } from "@/types/JobView";

interface JobProgressProps {
  readonly job: JobView;
}

/**
 * The one job, while it runs and after it stops.
 *
 * A pair rather than a percentage where there is one — "works 4 of 14" says something a bar alone
 * cannot — and the phase on its own where there is not, because rebuilding the catalog is a single
 * transaction with no natural tick to count.
 */
export function JobProgress({ job }: JobProgressProps): ReactElement {
  const percent = job.total > 0 ? Math.round((job.done / job.total) * 100) : null;
  return (
    <section className="job" data-state={job.state}>
      <p className="job__kind">{job.kind}</p>
      {job.state === "running" && (
        <>
          <p className="job__phase">{job.phase === "" ? "starting…" : job.phase}</p>
          {percent !== null && (
            <div
              className="job__bar"
              role="progressbar"
              aria-valuenow={job.done}
              aria-valuemin={0}
              aria-valuemax={job.total}
            >
              <span className="job__fill" style={{ width: `${String(percent)}%` }} />
            </div>
          )}
          {job.total > 0 && (
            <p className="job__count">
              {job.done} of {job.total}
            </p>
          )}
        </>
      )}
      {job.state === "done" && <p className="job__detail">Finished — {job.detail}</p>}
      {job.state === "failed" && <p className="job__error">Stopped — {job.error}</p>}
    </section>
  );
}
