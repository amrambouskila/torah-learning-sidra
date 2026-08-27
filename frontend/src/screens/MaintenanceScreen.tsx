import { useEffect, useState, type ReactElement } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { JobProgress } from "@/components/JobProgress";
import { RestoreDialog } from "@/components/RestoreDialog";
import { api } from "@/api/endpoints";
import { useAppDispatch } from "@/hooks/useAppDispatch";
import { useAppSelector } from "@/hooks/useAppSelector";
import { pollJob } from "@/stores/jobSlice";
import { loadMaintenance } from "@/stores/maintenanceSlice";
import { pushToast } from "@/stores/toastSlice";
import { failureMessage } from "@/utils/failureMessage";
import { writtenAt } from "@/utils/writtenAt";

const POLL_MS = 1000;

/**
 * The verbs that used to need a terminal.
 *
 * Six of the nine, and the three that are missing are missing on purpose: the launcher already
 * creates the schema on boot, and rewriting the sidra from YAML or replacing the ledger from an
 * arbitrary file both clear every advance on record. Those stay in the CLI. The one exception is
 * Restore, which reads the safety copy a correction wrote and no other file — it is the only
 * button here that can destroy learning, and it exists to undo the only other one that can.
 */
export function MaintenanceScreen(): ReactElement {
  const dispatch = useAppDispatch();
  const { data: status, error, isConflict } = useAppSelector((state) => state.maintenance);
  const job = useAppSelector((state) => state.job.data);
  const [busy, setBusy] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [start, setStart] = useState("");
  const [includeLinks, setIncludeLinks] = useState(true);
  const [failures, setFailures] = useState<readonly string[] | null>(null);

  useEffect(() => {
    void dispatch(loadMaintenance(undefined));
    void dispatch(pollJob(undefined));
  }, [dispatch]);

  // Bound once: read twice below, and inside a handler the optional chain would never narrow.
  const safetyCopyAt = status?.safety_copy_at ?? null;
  const jobState = job?.state ?? null;
  const jobStartedAt = job?.started_at ?? null;
  const running = jobState === "running";

  // Only while something is in flight: a screen that polls an idle app forever is a screen that
  // keeps the disk spinning for nothing.
  useEffect(() => {
    if (!running) return undefined;
    const timer = setInterval(() => {
      void dispatch(pollJob(undefined));
    }, POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [dispatch, running]);

  // When a job ends the counts behind it have moved, so read them once rather than every tick.
  useEffect(() => {
    if (jobState !== null && jobState !== "running") void dispatch(loadMaintenance(undefined));
  }, [dispatch, jobState, jobStartedAt]);

  const press = (name: string, action: () => Promise<unknown>, said: (result: never) => string): void => {
    setBusy(name);
    void action()
      .then((result) => {
        dispatch(pushToast(said(result as never), "success"));
        void dispatch(loadMaintenance(undefined));
        void dispatch(pollJob(undefined));
        return result;
      })
      .catch((caught: unknown) => {
        dispatch(pushToast(failureMessage(caught, `${name} did not work.`), "failure"));
      })
      .finally(() => {
        setBusy(null);
      });
  };

  if (error !== null) {
    return (
      <section className="screen">
        <h1 className="screen__title">Maintenance</h1>
        <ErrorBanner message={error} isConflict={isConflict} />
      </section>
    );
  }

  const disabled = running || busy !== null;

  return (
    <section className="screen">
      <h1 className="screen__title">Maintenance</h1>
      <p className="screen__lede">
        The commands that used to need a terminal. Rewriting the sidra and replacing the ledger from
        a file are not here — both erase every advance on record, and they stay in the CLI.
      </p>

      {job !== null && <JobProgress job={job} />}

      <section className="panel">
        <h2 className="panel__title">Ledger</h2>
        <p className="panel__note">
          The catalog rebuilds from the committed snapshot; the ledger cannot, because every advance
          exists nowhere but this database — and that database lives in a Docker volume, not in the
          project folder.
        </p>
        <p className="panel__stat">
          {status === null
            ? "…"
            : `${String(status.tracks)} tracks, ${String(status.advances)} advances`}
        </p>
        <p className="panel__stat">Last exported: {writtenAt(status?.ledger_exported_at ?? null)}</p>
        <button
          type="button"
          className="panel__action"
          disabled={disabled}
          onClick={() => {
            press("Export", api.exportLedger, (result: { advances: number }) => `Exported ${String(result.advances)} advances.`);
          }}
        >
          Export ledger
        </button>
      </section>

      <section className="panel">
        <h2 className="panel__title">Catalog</h2>
        <p className="panel__stat">
          {status === null
            ? "…"
            : `${String(status.works)} works, ${String(status.stored_units)} stored units`}
        </p>
        <button
          type="button"
          className="panel__action"
          disabled={disabled}
          onClick={() => {
            setFailures(null);
            press("Check", api.verifyCatalog, (result: { matches: boolean; failures: readonly string[] }) => {
              setFailures(result.failures);
              return result.matches ? "The catalog matches every expected count." : `${String(result.failures.length)} mismatches.`;
            });
          }}
        >
          Check counts
        </button>
        <button
          type="button"
          className="panel__action"
          disabled={disabled}
          onClick={() => {
            press("Rebuild", api.seedCatalog, () => "Rebuilding the catalog…");
          }}
        >
          Rebuild from snapshot
        </button>
        {failures !== null && failures.length > 0 && (
          <ul className="panel__failures">
            {failures.map((failure) => (
              <li key={failure}>{failure}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h2 className="panel__title">Calendar</h2>
        <p className="panel__note">
          One Sefaria call per day, throttled — a yearly cycle takes several minutes, and it needs
          at least 380 days to close.
        </p>
        <label className="panel__field">
          <span className="eyebrow">First day</span>
          <input
            type="date"
            value={start}
            onChange={(event) => {
              setStart(event.target.value);
            }}
          />
        </label>
        <button
          type="button"
          className="panel__action"
          disabled={disabled || start === ""}
          onClick={() => {
            press("Fetch", () => api.fetchCalendar(start, 400), () => "Fetching the calendar…");
          }}
        >
          Fetch 400 days
        </button>
      </section>

      <section className="panel">
        <h2 className="panel__title">Snapshot</h2>
        <p className="panel__note">
          Re-crawls Sefaria and writes a new snapshot. Deliberate: with links it pulls about 656 MB
          and takes a minute and a half.
        </p>
        <label className="panel__field panel__field--inline">
          <input
            type="checkbox"
            checked={includeLinks}
            onChange={(event) => {
              setIncludeLinks(event.target.checked);
            }}
          />
          <span className="eyebrow">Include the Ein Mishpat links</span>
        </label>
        <button
          type="button"
          className="panel__action"
          disabled={disabled}
          onClick={() => {
            press("Re-crawl", () => api.refreshSnapshot(includeLinks), () => "Re-crawling Sefaria…");
          }}
        >
          Re-crawl Sefaria
        </button>
      </section>

      <section className="panel panel--danger">
        <h2 className="panel__title">Recovery</h2>
        <p className="panel__note">
          A correction writes the whole ledger out before it deletes anything. This puts it back —
          that one file and no other. Everything recorded since it was written is lost.
        </p>
        <p className="panel__stat">Safety copy: {writtenAt(safetyCopyAt)}</p>
        <button
          type="button"
          className="panel__action panel__action--danger"
          disabled={disabled || safetyCopyAt === null}
          onClick={() => {
            setRestoring(true);
          }}
        >
          Restore from the safety copy
        </button>
      </section>

      {restoring && (
        <RestoreDialog
          writtenAt={safetyCopyAt}
          onConfirm={(word) => {
            setRestoring(false);
            press("Restore", () => api.restoreLedger(word), (result: { advances: number }) => `Restored ${String(result.advances)} advances.`);
          }}
          onCancel={() => {
            setRestoring(false);
          }}
        />
      )}
    </section>
  );
}
