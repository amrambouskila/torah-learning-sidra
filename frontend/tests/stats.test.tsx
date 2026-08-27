import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { StatsScreen } from "@/screens/StatsScreen";
import { createStore } from "@/stores/store";
import type { StatsResponse, StatsTrack } from "@/types/StatsResponse";

function statsTrack(overrides: Partial<StatsTrack> = {}): StatsTrack {
  return {
    track_id: "t-gemara",
    name_en: "Gemara",
    name_he: "גמרא",
    unit_singular: "amud",
    unit_plural: "amudim",
    debt_now: 22,
    debt_then: 20,
    learned_units: 0,
    days_learned: 0,
    last_learned_on: null,
    opened_on: null,
    net: [0, 1, 1],
    ...overrides,
  };
}

const NEVIIM = statsTrack({
  track_id: "t-neviim",
  name_en: "Neviim",
  name_he: "נביאים",
  unit_singular: "perek",
  unit_plural: "perakim",
  debt_now: 1,
  debt_then: 3,
  learned_units: 4,
  days_learned: 1,
  opened_on: "2026-08-25",
  net: [0, -3, 1],
});

const CHAVRUSA = statsTrack({
  track_id: "t-cohen",
  name_en: "David Cohen — Mishneh Torah",
  name_he: "דוד כהן",
  debt_now: null,
  debt_then: null,
  net: [0, 0, 0],
});

function body(overrides: Partial<StatsResponse> = {}): StatsResponse {
  return {
    on: "2026-08-26",
    days: ["2026-08-24", "2026-08-25", "2026-08-26"],
    window_days: 3,
    requested_window_days: 30,
    standing: { behind: 2, on_pace: 6, ahead: 0, not_started: 7, chavrusa: 5 },
    streak: { current: 2, longest: 4 },
    tracks: [statsTrack(), NEVIIM, CHAVRUSA],
    ...overrides,
  };
}

function renderStats() {
  render(
    <Provider store={createStore()}>
      <MemoryRouter>
        <StatsScreen />
      </MemoryRouter>
    </Provider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("StatsScreen", () => {
  it("counts the sidra in tracks, never in units", async () => {
    // 21 amudim plus 4 perakim is not 25 of anything.
    vi.spyOn(api, "stats").mockResolvedValue(body());
    renderStats();
    for (const label of ["behind", "on pace", "ahead", "waiting", "chavrusa"]) {
      expect(await screen.findByText(label)).toBeInTheDocument();
    }
  });

  it("says plainly that the window is shorter than asked for", async () => {
    // A ninety-column grid with three lit columns is not a report, it is an apology.
    vi.spyOn(api, "stats").mockResolvedValue(body());
    renderStats();
    expect(await screen.findByText(/the ledger is not older than that/)).toBeInTheDocument();
  });

  it("hides the clamp note once the ledger is old enough", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(body({ window_days: 30, requested_window_days: 30 }));
    renderStats();
    await screen.findByText("behind");
    expect(screen.queryByText(/not older than that/)).not.toBeInTheDocument();
  });

  it("reads a widening gap and a closing one in the ledger's own units", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(body());
    renderStats();
    expect(await screen.findByText("opened 2 amudim")).toBeInTheDocument();
    expect(screen.getByText("closed 2 perakim")).toBeInTheDocument();
  });

  it("marks each day by whether the gap opened, closed or held", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(body());
    renderStats();
    const row = (await screen.findByText("Neviim")).closest("tr") as HTMLElement;
    const states = [...row.querySelectorAll(".stats__cell")].map((cell) =>
      cell.getAttribute("data-state"),
    );
    expect(states).toEqual(["held", "closed", "opened"]);
  });

  it("gives a chavrusa track no debt movement, because it carries staleness instead", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(body());
    renderStats();
    const row = (await screen.findByText("David Cohen — Mishneh Torah")).closest("tr") as HTMLElement;
    expect(within(row).getByText("—")).toBeInTheDocument();
  });

  it("shows a streak that counts yesterday, and its best", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(body());
    renderStats();
    expect(await screen.findByText(/days running/)).toBeInTheDocument();
    expect(screen.getByText(/best 4/)).toBeInTheDocument();
  });

  it("does not brag about a best that equals the current run", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(body({ streak: { current: 1, longest: 1 } }));
    renderStats();
    expect(await screen.findByText(/day running/)).toBeInTheDocument();
    expect(screen.queryByText(/best/)).not.toBeInTheDocument();
  });

  it("puts the untouched tracks first, then the deepest debt", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(body());
    renderStats();
    await screen.findByText("Gemara");
    const names = [...document.querySelectorAll("tbody .gloss")].map((cell) => cell.textContent);
    expect(names).toEqual(["Gemara", "David Cohen — Mishneh Torah", "Neviim"]);
  });

  it("breaks a tie between equal debts by name", async () => {
    const twin = statsTrack({ track_id: "t-twin", name_en: "Aleph", name_he: "אלף", debt_now: 22 });
    vi.spyOn(api, "stats").mockResolvedValue(body({ tracks: [statsTrack(), twin] }));
    renderStats();
    await screen.findByText("Gemara");
    const names = [...document.querySelectorAll("tbody .gloss")].map((cell) => cell.textContent);
    expect(names).toEqual(["Aleph", "Gemara"]);
  });

  it("holds a day the server sent no value for", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(body({ tracks: [statsTrack({ net: [1] })] }));
    renderStats();
    const row = (await screen.findByText("Gemara")).closest("tr") as HTMLElement;
    const states = [...row.querySelectorAll(".stats__cell")].map((cell) =>
      cell.getAttribute("data-state"),
    );
    expect(states).toEqual(["opened", "held", "held"]);
  });

  it("names a single unit and a single day in the singular", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(
      body({
        tracks: [
          statsTrack({ debt_now: 21, debt_then: 20, learned_units: 1, days_learned: 1, net: [0, 0, 1] }),
        ],
      }),
    );
    renderStats();
    expect(await screen.findByText("opened 1 amud")).toBeInTheDocument();
    const row = (await screen.findByText("Gemara")).closest("tr") as HTMLElement;
    expect(row.textContent).toContain("1 amud on 1 day");
  });

  it("says a track held its ground when the gap neither opened nor closed", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(
      body({
        tracks: [statsTrack({ debt_now: 0, debt_then: 0, learned_units: 3, days_learned: 3, net: [0, 0, 0] })],
      }),
    );
    renderStats();
    const row = (await screen.findByText("Gemara")).closest("tr") as HTMLElement;
    // "held" also labels each cell for a screen reader, so read the summary column itself.
    const summary = row.querySelector(".stats__movement") as HTMLElement;
    expect(summary.textContent).toContain("held");
    expect(summary.textContent).toContain("3 amudim on 3 days");
  });

  it("shows a single date when the window is one day wide", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(
      body({ days: ["2026-08-26"], window_days: 1, tracks: [statsTrack({ net: [1] })] }),
    );
    renderStats();
    await screen.findByText("Gemara");
    expect(screen.getAllByText("2026-08-26")).toHaveLength(1);
  });

  it("asks the server again when the window changes", async () => {
    const spy = vi.spyOn(api, "stats").mockResolvedValue(body());
    renderStats();
    await screen.findByText("behind");
    await userEvent.click(screen.getByRole("button", { name: "7 days" }));
    expect(spy).toHaveBeenLastCalledWith(7);
  });

  it("says so when nothing has begun rather than drawing an empty grid", async () => {
    vi.spyOn(api, "stats").mockResolvedValue(body({ tracks: [] }));
    renderStats();
    expect(await screen.findByText(/Nothing has begun yet/)).toBeInTheDocument();
  });

  it("keeps the backend's sentence on failure", async () => {
    vi.spyOn(api, "stats").mockRejectedValue(new ApiError("no calendar snapshot for 2027-10-01", 409));
    renderStats();
    expect(await screen.findByRole("alert")).toHaveTextContent("no calendar snapshot");
  });
});
