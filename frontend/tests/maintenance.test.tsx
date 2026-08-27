/**
 * The verbs that used to need a terminal.
 *
 * Six of the nine are buttons here; the three that clear the ledger are not, and the one narrow
 * exception — Restore — is typed rather than clicked, because everything recorded since the safety
 * copy was written goes with it.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { JobProgress } from "@/components/JobProgress";
import { RestoreDialog } from "@/components/RestoreDialog";
import { ToastStack } from "@/components/ToastStack";
import { MaintenanceScreen } from "@/screens/MaintenanceScreen";
import { createStore } from "@/stores/store";
import type { ExportResult } from "@/types/ExportResult";
import type { JobView } from "@/types/JobView";
import type { MaintenanceStatus } from "@/types/MaintenanceStatus";
import { writtenAt } from "@/utils/writtenAt";

const STATUS: MaintenanceStatus = {
  catalog_seeded: true,
  ledger_seeded: true,
  works: 279,
  stored_units: 432,
  tracks: 20,
  advances: 25,
  ledger_exported_at: null,
  safety_copy_at: null,
};

const MOVED: ExportResult = {
  path: "/app/data/ledger.json",
  tracks: 20,
  advances: 25,
  chavrusas: 5,
  tags: 3,
  calendar_days: 400,
};

function job(overrides: Partial<JobView> = {}): JobView {
  return {
    kind: "refresh",
    state: "running",
    phase: "crawling bavli",
    done: 4,
    total: 14,
    started_at: "2026-08-27T12:00:00Z",
    finished_at: null,
    detail: "",
    error: "",
    ...overrides,
  };
}

function mount(): void {
  render(
    <Provider store={createStore()}>
      <MemoryRouter>
        <MaintenanceScreen />
        <ToastStack />
      </MemoryRouter>
    </Provider>,
  );
}

beforeEach(() => {
  vi.spyOn(api, "maintenance").mockResolvedValue(STATUS);
  vi.spyOn(api, "job").mockResolvedValue(null);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// --- what it shows -------------------------------------------------------------------------------

describe("the Maintenance screen", () => {
  it("reports both halves of the database", async () => {
    mount();
    expect(await screen.findByText(/20 tracks, 25 advances/)).toBeInTheDocument();
    expect(screen.getByText(/279 works, 432 stored units/)).toBeInTheDocument();
  });

  it("says plainly when nothing has ever been exported", async () => {
    mount();
    expect(await screen.findByText(/Last exported: never/)).toBeInTheDocument();
  });

  it("offers no way to rewrite the sidra or replace the ledger from a file", async () => {
    // Both call clear_ledger. They stay in the CLI, and the screen must not grow a door to them.
    mount();
    await screen.findByText(/20 tracks/);
    expect(screen.queryByRole("button", { name: /seed.tracks/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Import/i })).not.toBeInTheDocument();
  });

  it("surfaces a failure to read the status at all", async () => {
    vi.spyOn(api, "maintenance").mockRejectedValue(new ApiError("no database", 409));
    mount();
    expect(await screen.findByText("no database")).toBeInTheDocument();
  });
});

// --- the fast buttons ----------------------------------------------------------------------------

describe("export", () => {
  it("writes the ledger and says what it wrote", async () => {
    vi.spyOn(api, "exportLedger").mockResolvedValue(MOVED);
    mount();

    await userEvent.click(await screen.findByRole("button", { name: "Export ledger" }));

    expect(api.exportLedger).toHaveBeenCalled();
    expect(await screen.findByText(/Exported 25 advances/)).toBeInTheDocument();
  });

  it("surfaces a refusal", async () => {
    vi.spyOn(api, "exportLedger").mockRejectedValue(new ApiError("the disk is full", 409));
    mount();

    await userEvent.click(await screen.findByRole("button", { name: "Export ledger" }));

    expect(await screen.findByText("the disk is full")).toBeInTheDocument();
  });
});

describe("verify", () => {
  it("lists the mismatches rather than an exit code", async () => {
    vi.spyOn(api, "verifyCatalog").mockResolvedValue({
      matches: false,
      failures: ["bavli: 5348 amudim, expected 5349"],
    });
    mount();

    await userEvent.click(await screen.findByRole("button", { name: "Check counts" }));

    expect(await screen.findByText("bavli: 5348 amudim, expected 5349")).toBeInTheDocument();
    expect(await screen.findByText(/1 mismatches/)).toBeInTheDocument();
  });

  it("says so when the catalog is good", async () => {
    vi.spyOn(api, "verifyCatalog").mockResolvedValue({ matches: true, failures: [] });
    mount();

    await userEvent.click(await screen.findByRole("button", { name: "Check counts" }));

    expect(await screen.findByText(/matches every expected count/)).toBeInTheDocument();
  });
});

// --- the jobs ------------------------------------------------------------------------------------

describe("the one job slot", () => {
  it("starts a rebuild and says it is running", async () => {
    vi.spyOn(api, "seedCatalog").mockResolvedValue(job({ kind: "seed" }));
    mount();

    await userEvent.click(await screen.findByRole("button", { name: "Rebuild from snapshot" }));

    expect(api.seedCatalog).toHaveBeenCalled();
    expect(await screen.findByText(/Rebuilding the catalog/)).toBeInTheDocument();
  });

  it("asks for the span before it will fetch a calendar", async () => {
    mount();
    const fetch = await screen.findByRole("button", { name: "Fetch 400 days" });
    expect(fetch).toBeDisabled();

    await userEvent.type(screen.getByLabelText("First day"), "2026-10-01");

    expect(fetch).toBeEnabled();
  });

  it("sends the day he picked and the full cycle", async () => {
    vi.spyOn(api, "fetchCalendar").mockResolvedValue(job({ kind: "calendar" }));
    mount();
    await userEvent.type(await screen.findByLabelText("First day"), "2026-10-01");

    await userEvent.click(screen.getByRole("button", { name: "Fetch 400 days" }));

    expect(api.fetchCalendar).toHaveBeenCalledWith("2026-10-01", 400);
  });

  it("lets him skip the 656 MB of links", async () => {
    vi.spyOn(api, "refreshSnapshot").mockResolvedValue(job());
    mount();
    await userEvent.click(await screen.findByLabelText(/Include the Ein Mishpat links/));

    await userEvent.click(screen.getByRole("button", { name: "Re-crawl Sefaria" }));

    expect(api.refreshSnapshot).toHaveBeenCalledWith(false);
  });

  it("includes the links by default", async () => {
    vi.spyOn(api, "refreshSnapshot").mockResolvedValue(job());
    mount();

    await userEvent.click(await screen.findByRole("button", { name: "Re-crawl Sefaria" }));

    expect(api.refreshSnapshot).toHaveBeenCalledWith(true);
  });

  it("disables every button while a job runs, so two cannot be started", async () => {
    vi.spyOn(api, "job").mockResolvedValue(job());
    mount();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Export ledger" })).toBeDisabled();
    });
    expect(screen.getByRole("button", { name: "Re-crawl Sefaria" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Rebuild from snapshot" })).toBeDisabled();
  });

  it("surfaces the refusal when the slot is already taken", async () => {
    vi.spyOn(api, "seedCatalog").mockRejectedValue(
      new ApiError("a refresh job is already running; wait for it to finish", 409),
    );
    mount();

    await userEvent.click(await screen.findByRole("button", { name: "Rebuild from snapshot" }));

    expect(await screen.findByText(/a refresh job is already running/)).toBeInTheDocument();
  });
});

// --- the progress itself -------------------------------------------------------------------------

describe("JobProgress", () => {
  it("shows a pair as well as a bar, because the pair says more", () => {
    render(<JobProgress job={job()} />);
    expect(screen.getByText("crawling bavli")).toBeInTheDocument();
    expect(screen.getByText(/4 of 14/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "4");
  });

  it("shows the phase alone when there is no natural tick to count", () => {
    render(<JobProgress job={job({ kind: "seed", phase: "writing the catalog", done: 0, total: 0 })} />);
    expect(screen.getByText("writing the catalog")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("says starting when a job has not reported anything yet", () => {
    render(<JobProgress job={job({ phase: "", done: 0, total: 0 })} />);
    expect(screen.getByText(/starting/)).toBeInTheDocument();
  });

  it("reports what a finished job achieved", () => {
    render(<JobProgress job={job({ state: "done", detail: "279 works, 27,252 units" })} />);
    expect(screen.getByText(/Finished — 279 works/)).toBeInTheDocument();
  });

  it("reports why a stopped job stopped", () => {
    render(<JobProgress job={job({ state: "failed", error: "ReadTimeout: Sefaria" })} />);
    expect(screen.getByText(/Stopped — ReadTimeout: Sefaria/)).toBeInTheDocument();
  });
});

// --- recovery ------------------------------------------------------------------------------------

describe("restore", () => {
  it("is offered only once a correction has written something to go back to", async () => {
    mount();
    expect(await screen.findByRole("button", { name: /Restore from the safety copy/ })).toBeDisabled();
  });

  it("will not act on a word half typed", async () => {
    vi.spyOn(api, "maintenance").mockResolvedValue({ ...STATUS, safety_copy_at: "2026-08-27T12:00:00Z" });
    mount();

    await userEvent.click(await screen.findByRole("button", { name: /Restore from the safety copy/ }));
    await userEvent.type(screen.getByLabelText(/Type RESTORE to continue/), "restore");

    expect(screen.getByRole("button", { name: "Restore" })).toBeDisabled();
  });

  it("puts the ledger back once the word is typed in full", async () => {
    vi.spyOn(api, "maintenance").mockResolvedValue({ ...STATUS, safety_copy_at: "2026-08-27T12:00:00Z" });
    vi.spyOn(api, "restoreLedger").mockResolvedValue(MOVED);
    mount();

    await userEvent.click(await screen.findByRole("button", { name: /Restore from the safety copy/ }));
    await userEvent.type(screen.getByLabelText(/Type RESTORE to continue/), "RESTORE");
    await userEvent.click(screen.getByRole("button", { name: "Restore" }));

    expect(api.restoreLedger).toHaveBeenCalledWith("RESTORE");
    expect(await screen.findByText(/Restored 25 advances/)).toBeInTheDocument();
  });

  it("can be backed out of", async () => {
    vi.spyOn(api, "maintenance").mockResolvedValue({ ...STATUS, safety_copy_at: "2026-08-27T12:00:00Z" });
    vi.spyOn(api, "restoreLedger");
    mount();

    await userEvent.click(await screen.findByRole("button", { name: /Restore from the safety copy/ }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(api.restoreLedger).not.toHaveBeenCalled();
  });

  it("names what is about to be lost", () => {
    render(<RestoreDialog writtenAt="2026-08-27T12:00:00Z" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/Anything\s+learned since then is lost/)).toBeInTheDocument();
  });

  it("copes with a safety copy whose date is unknown", () => {
    render(<RestoreDialog writtenAt={null} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/written never/)).toBeInTheDocument();
  });
});

describe("writtenAt", () => {
  it('says "never" rather than a dash, because the difference matters here', () => {
    expect(writtenAt(null)).toBe("never");
  });

  it("renders a real timestamp as a date and a time", () => {
    expect(writtenAt("2026-08-27T12:00:00Z")).toMatch(/\d/);
  });
});

describe("polling", () => {
  it("keeps asking while a job runs, and stops once it ends", async () => {
    // Only while something is in flight: polling an idle app forever keeps the disk spinning.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      vi.spyOn(api, "job").mockResolvedValue(job());
      mount();
      await waitFor(() => {
        expect(screen.getByText("crawling bavli")).toBeInTheDocument();
      });
      const before = vi.mocked(api.job).mock.calls.length;

      await vi.advanceTimersByTimeAsync(3000);

      expect(vi.mocked(api.job).mock.calls.length).toBeGreaterThan(before);
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not poll when nothing is running", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      vi.spyOn(api, "job").mockResolvedValue(job({ state: "done", detail: "279 works" }));
      mount();
      await waitFor(() => {
        expect(screen.getByText(/Finished — 279 works/)).toBeInTheDocument();
      });
      const before = vi.mocked(api.job).mock.calls.length;

      await vi.advanceTimersByTimeAsync(5000);

      expect(vi.mocked(api.job).mock.calls.length).toBe(before);
    } finally {
      vi.useRealTimers();
    }
  });
});
