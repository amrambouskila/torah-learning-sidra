/** Setting, moving and clearing a track's start date, from both screens. */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { StartDateDialog } from "@/components/StartDateDialog";
import { ToastStack } from "@/components/ToastStack";
import { TodayScreen } from "@/screens/TodayScreen";
import { TrackScreen } from "@/screens/TrackScreen";
import { createStore } from "@/stores/store";
import { setTrackStart } from "@/stores/tracksSlice";
import { debtPhrase } from "@/utils/debtPhrase";
import { startDateLabel } from "@/utils/startDateLabel";

import { GEMARA, HADAR, LIKUTEI, today, track } from "./fixtures";

afterEach(() => {
  vi.restoreAllMocks();
});

// --- how a countdown reads --------------------------------------------------------------------

describe("debtPhrase while a track waits", () => {
  it.each([
    [1, "1", "day away"],
    [3, "3", "days away"],
    [6, "6", "days away"],
    [7, "1", "week away"],
    [14, "2", "weeks away"],
    [47, "7", "weeks away"],
  ])("reads %i days as %s %s", (days, value, suffix) => {
    // Six days must not round up to "1 week away" — that was harmless only while every start
    // date was seven weeks out.
    const phrase = debtPhrase(track({ starts_in_days: days, starts_on: "2026-10-11" }));
    expect(phrase.tone).toBe("waiting");
    expect(phrase.value).toBe(value);
    expect(phrase.suffix).toBe(suffix);
  });
});

describe("startDateLabel", () => {
  it("offers to set one when there is none, and to change one when there is", () => {
    expect(startDateLabel(track({ starts_on: null }))).toBe("Set start");
    expect(startDateLabel(track({ starts_on: "2026-10-11" }))).toBe("Start date");
  });
});

// --- the dialog ---------------------------------------------------------------------------------

describe("StartDateDialog", () => {
  it("prefills the date the track already has", () => {
    render(
      <StartDateDialog track={LIKUTEI} today="2026-08-25" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByLabelText("Starts on")).toHaveValue("2026-10-11");
  });

  it("suggests a week out when the track has none", () => {
    render(
      <StartDateDialog
        track={track({ starts_on: null })}
        today="2026-08-25"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Starts on")).toHaveValue("2026-09-01");
  });

  it("refuses to offer a day in the past", () => {
    render(
      <StartDateDialog track={LIKUTEI} today="2026-08-25" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByLabelText("Starts on")).toHaveAttribute("min", "2026-08-25");
  });

  it.each([
    ["Tomorrow", "2026-08-26"],
    ["In a week", "2026-09-01"],
    ["In two weeks", "2026-09-08"],
    ["In a month", "2026-09-24"],
  ])("the %s preset picks %s", async (label, expected) => {
    const onConfirm = vi.fn();
    render(
      <StartDateDialog track={LIKUTEI} today="2026-08-25" onConfirm={onConfirm} onCancel={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: label }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onConfirm).toHaveBeenCalledWith(expected, false);
  });

  it("takes a typed date", async () => {
    const onConfirm = vi.fn();
    render(
      <StartDateDialog track={LIKUTEI} today="2026-08-25" onConfirm={onConfirm} onCancel={vi.fn()} />,
    );
    await userEvent.clear(screen.getByLabelText("Starts on"));
    await userEvent.type(screen.getByLabelText("Starts on"), "2026-09-08");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onConfirm).toHaveBeenCalledWith("2026-09-08", false);
  });

  it("offers to start the track now, clearing the date", async () => {
    const onConfirm = vi.fn();
    render(
      <StartDateDialog track={LIKUTEI} today="2026-08-25" onConfirm={onConfirm} onCancel={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Start it now" }));
    expect(onConfirm).toHaveBeenCalledWith(null, false);
  });

  it("offers no clear on a track that has no start date to clear", () => {
    render(
      <StartDateDialog
        track={track({ starts_on: null })}
        today="2026-08-25"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: "Start it now" })).not.toBeInTheDocument();
  });

  it("says what the start day means", () => {
    render(
      <StartDateDialog track={LIKUTEI} today="2026-08-25" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByText(/first parsha is due on it/)).toBeInTheDocument();
  });

  it("cancels without confirming", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <StartDateDialog track={LIKUTEI} today="2026-08-25" onConfirm={onConfirm} onCancel={onCancel} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

// --- the store -----------------------------------------------------------------------------------

describe("setTrackStart", () => {
  it("swaps in the recomputed row", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([LIKUTEI, GEMARA]);
    vi.spyOn(api, "setStart").mockResolvedValue({ ...LIKUTEI, starts_on: "2026-09-01", starts_in_days: 7 });
    const store = createStore();
    const { loadTracks } = await import("@/stores/tracksSlice");
    await store.dispatch(loadTracks(undefined));
    await store.dispatch(setTrackStart({ trackId: LIKUTEI.id, startsOn: "2026-09-01" }));

    expect(store.getState().tracks.data[0]?.starts_on).toBe("2026-09-01");
    expect(store.getState().tracks.data[1]?.name_en).toBe("Gemara");
  });

  it("keeps the backend's refusal intact", async () => {
    vi.spyOn(api, "setStart").mockRejectedValue(
      new ApiError("Neviim is already being learned; changing its start date would forgive what it owes", 422),
    );
    const store = createStore();
    const result = await store.dispatch(setTrackStart({ trackId: "t1", startsOn: "2026-09-01" }));
    expect(result.type).toBe("tracks/setStart/rejected");
  });
});

// --- Today ---------------------------------------------------------------------------------------

function renderToday() {
  render(
    <Provider store={createStore()}>
      <MemoryRouter>
        <TodayScreen />
        <ToastStack />
      </MemoryRouter>
    </Provider>,
  );
}

describe("TodayScreen", () => {
  it("offers the control on a scheduled track and not on a chavrusa one", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [], shabbat: [LIKUTEI], chavrusa: [HADAR] }));
    renderToday();
    const likutei = (await screen.findByText("Likutei Sichot")).closest(".card");
    expect(within(likutei as HTMLElement).getByRole("button", { name: "Start date" })).toBeInTheDocument();

    const hadar = screen.getByText("David Hadar — Brachot").closest(".card");
    expect(within(hadar as HTMLElement).queryByRole("button", { name: /start/i })).not.toBeInTheDocument();
  });

  it("saves a start date and refetches", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [], shabbat: [LIKUTEI], chavrusa: [] }));
    const setStart = vi
      .spyOn(api, "setStart")
      .mockResolvedValue({ ...LIKUTEI, starts_on: "2026-09-01", starts_in_days: 7 });
    renderToday();

    await userEvent.click(await screen.findByRole("button", { name: "Start date" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "In a week" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));

    expect(setStart).toHaveBeenCalledWith("t-likutei", "2026-09-01", false);
    expect(await screen.findByText(/starts 2026-09-01/)).toBeInTheDocument();
    await waitFor(() => {
      expect(vi.mocked(api.today).mock.calls.length).toBeGreaterThan(1);
    });
  });

  it("says so when a track is started now", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [], shabbat: [LIKUTEI], chavrusa: [] }));
    vi.spyOn(api, "setStart").mockResolvedValue({ ...LIKUTEI, starts_on: null, starts_in_days: null });
    renderToday();
    await userEvent.click(await screen.findByRole("button", { name: "Start date" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Start it now" }));
    expect(await screen.findByText(/starts now/)).toBeInTheDocument();
  });

  it("surfaces the backend's refusal as a toast", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [], shabbat: [LIKUTEI], chavrusa: [] }));
    vi.spyOn(api, "setStart").mockRejectedValue(new ApiError("is already being learned", 422));
    renderToday();
    await userEvent.click(await screen.findByRole("button", { name: "Start date" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("is already being learned")).toBeInTheDocument();
  });

  it("closes the dialog on cancel without saving", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [], shabbat: [LIKUTEI], chavrusa: [] }));
    const setStart = vi.spyOn(api, "setStart");
    renderToday();
    await userEvent.click(await screen.findByRole("button", { name: "Start date" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(setStart).not.toHaveBeenCalled();
  });
});

// --- the Track screen -----------------------------------------------------------------------------

function renderTrack() {
  render(
    <Provider store={createStore()}>
      <MemoryRouter initialEntries={["/tracks/t-likutei"]}>
        <Routes>
          <Route path="/tracks/:trackId" element={<TrackScreen />} />
        </Routes>
        <ToastStack />
      </MemoryRouter>
    </Provider>,
  );
}

describe("TrackScreen", () => {
  it("shows the start date among the facts", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: LIKUTEI, rail: [], rail_from: 0, rail_to: 0 });
    vi.spyOn(api, "rail").mockResolvedValue([]);
    renderTrack();
    expect(await screen.findByText("Starts")).toBeInTheDocument();
    expect(screen.getByText("2026-10-11")).toBeInTheDocument();
  });

  it("says plainly when there is no start date", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    vi.spyOn(api, "rail").mockResolvedValue([]);
    renderTrack();
    expect(await screen.findByText("no start date")).toBeInTheDocument();
  });

  it("saves a new date and updates in place", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: LIKUTEI, rail: [], rail_from: 0, rail_to: 0 });
    vi.spyOn(api, "rail").mockResolvedValue([]);
    vi.spyOn(api, "setStart").mockResolvedValue({ ...LIKUTEI, starts_on: "2026-09-01" });
    renderTrack();
    await userEvent.click(await screen.findByRole("button", { name: "Start date" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/Starts 2026-09-01/)).toBeInTheDocument();
  });

  it("says so when it is started now", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: LIKUTEI, rail: [], rail_from: 0, rail_to: 0 });
    vi.spyOn(api, "rail").mockResolvedValue([]);
    vi.spyOn(api, "setStart").mockResolvedValue({ ...LIKUTEI, starts_on: null });
    renderTrack();
    await userEvent.click(await screen.findByRole("button", { name: "Start date" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Start it now" }));
    expect(await screen.findByText("Started now.")).toBeInTheDocument();
  });

  it("surfaces a refusal", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: LIKUTEI, rail: [], rail_from: 0, rail_to: 0 });
    vi.spyOn(api, "rail").mockResolvedValue([]);
    vi.spyOn(api, "setStart").mockRejectedValue(new ApiError("that date is in the past", 422));
    renderTrack();
    await userEvent.click(await screen.findByRole("button", { name: "Start date" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("that date is in the past")).toBeInTheDocument();
  });

  it("closes on cancel", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: LIKUTEI, rail: [], rail_from: 0, rail_to: 0 });
    vi.spyOn(api, "rail").mockResolvedValue([]);
    renderTrack();
    await userEvent.click(await screen.findByRole("button", { name: "Start date" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("offers no control on a chavrusa track", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: HADAR, rail: [], rail_from: 0, rail_to: 0 });
    vi.spyOn(api, "rail").mockResolvedValue([]);
    renderTrack();
    await screen.findByText("no schedule");
    expect(screen.queryByRole("button", { name: /start/i })).not.toBeInTheDocument();
  });
});


// --- the backlog warning -----------------------------------------------------------------------

describe("clearing a backlog", () => {
  it("says nothing when the track owes nothing", () => {
    // Likutey Moharan's shape: seeded at its first unit from the old note, so it has a position
    // but has never actually been learned. Nothing to clear, nothing to warn about.
    render(
      <StartDateDialog
        track={track({ actual_ordinal: 1, debt: 0, starts_on: null })}
        today="2026-08-25"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByText(/owes/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("says nothing when a never-opened track has only accrued", () => {
    render(
      <StartDateDialog
        track={track({ actual_ordinal: 0, debt: 4, starts_on: null })}
        today="2026-08-25"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByText(/owes/)).not.toBeInTheDocument();
  });

  it("names the backlog on a track being learned, and asks before clearing it", async () => {
    const onConfirm = vi.fn();
    render(
      <StartDateDialog
        track={track({ ...GEMARA, starts_on: null })}
        today="2026-08-25"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText(/owes 20 amudim/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear 20 and save" }));
    expect(onConfirm).toHaveBeenCalledWith(expect.any(String), true);
  });

  it("uses the singular for a backlog of one", () => {
    render(
      <StartDateDialog
        track={track({ actual_ordinal: 5, debt: 1, starts_on: null })}
        today="2026-08-25"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText(/owes 1 perek/)).toBeInTheDocument();
  });

  it("passes the acknowledgement to the server", async () => {
    const setStart = vi.spyOn(api, "setStart").mockResolvedValue(GEMARA);
    const store = createStore();
    await store.dispatch(setTrackStart({ trackId: "t1", startsOn: "2026-09-01", forgive: true }));
    expect(setStart).toHaveBeenCalledWith("t1", "2026-09-01", true);
  });

  it("defaults to withholding it", async () => {
    const setStart = vi.spyOn(api, "setStart").mockResolvedValue(GEMARA);
    const store = createStore();
    await store.dispatch(setTrackStart({ trackId: "t1", startsOn: "2026-09-01" }));
    expect(setStart).toHaveBeenCalledWith("t1", "2026-09-01", false);
  });
});
