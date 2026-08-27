/** The last few branches: an in-flight rail chunk, a failed track list, an empty ApiError. */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { Rail } from "@/components/Rail";
import { RoadmapScreen } from "@/screens/RoadmapScreen";
import { loadRoadmap } from "@/stores/roadmapSlice";
import { createStore } from "@/stores/store";
import { loadTracks } from "@/stores/tracksSlice";
import type { RailUnit } from "@/types/RailUnit";

afterEach(() => {
  vi.restoreAllMocks();
});

it("asks for an in-flight rail chunk only once", async () => {
  // Two scrolls into the same chunk before the first response lands must not double-fetch.
  const opened: ((units: RailUnit[]) => void)[] = [];
  const spy = vi.spyOn(api, "rail").mockReturnValue(
    new Promise<RailUnit[]>((resolve) => {
      opened.push(resolve);
    }),
  );

  const { rerender } = render(
    <Rail trackId="t1" total={50} actual={1} scheduled={null} onSelect={vi.fn()} />,
  );
  // Changing `total` re-runs the effect while the first request is still open, which is the
  // only way the same chunk gets asked for twice.
  rerender(<Rail trackId="t1" total={60} actual={1} scheduled={null} onSelect={vi.fn()} />);
  rerender(<Rail trackId="t1" total={70} actual={1} scheduled={null} onSelect={vi.fn()} />);
  await waitFor(() => {
    expect(spy).toHaveBeenCalledTimes(1);
  });

  for (const resolve of opened) resolve([]);
});

it("says something when a rejection carries neither a payload nor a message", async () => {
  // A hand-dispatched rejected action is the shape a reducer must still survive.
  const store = createStore();
  store.dispatch({ type: "roadmap/load/rejected", error: {} });
  await Promise.resolve();
  expect(store.getState().roadmap.error).toBe("The request failed.");
});

it("reports a failed track list", async () => {
  vi.spyOn(api, "tracks").mockRejectedValue(new ApiError("the catalog is empty", 409));
  const store = createStore();
  await store.dispatch(loadTracks(undefined));
  expect(store.getState().tracks.error).toBe("the catalog is empty");
  expect(store.getState().tracks.isConflict).toBe(true);
});

it("gives an ApiError with no message words of its own", async () => {
  vi.spyOn(api, "tracks").mockRejectedValue(new ApiError("", 500));
  const store = createStore();
  await store.dispatch(loadTracks(undefined));
  expect(store.getState().tracks.error).toBe("The request failed.");
});

it("pins the roadmap to a day when asked", async () => {
  const spy = vi.spyOn(api, "roadmap").mockResolvedValue([]);
  const store = createStore();
  await store.dispatch(loadRoadmap("2026-08-25"));
  expect(spy).toHaveBeenCalledWith({ on: "2026-08-25" });
});

it("orders two dated tracks by their finish dates", async () => {
  const row = {
    track_id: "a",
    name_en: "Later",
    name_he: "מאוחר",
    total: 10,
    actual_ordinal: 1,
    units_remaining: 9,
    rate_per_day: 1,
    debt: 0,
    projected_finish: "2027-12-01",
    work_ref_title: null,
    corpus_en: null,
    corpus_total: null,
    corpus_years: null,
    yearly_cycle_rate: 0.02,
  };
  vi.spyOn(api, "roadmap").mockResolvedValue([
    row,
    { ...row, track_id: "b", name_en: "Sooner", projected_finish: "2026-01-01" },
  ]);
  render(
    <Provider store={createStore()}>
      <MemoryRouter>
        <RoadmapScreen />
      </MemoryRouter>
    </Provider>,
  );
  await screen.findByText("2026-01-01");
  expect(screen.getAllByRole("row")[1]?.textContent).toContain("Sooner");
});

it("sorts by remaining with an undated track in the mix", async () => {
  const row = {
    track_id: "a",
    name_en: "Gemara",
    name_he: "גמרא",
    total: 10,
    actual_ordinal: 1,
    units_remaining: 9,
    rate_per_day: 1,
    debt: 0,
    projected_finish: "2026-12-01",
    work_ref_title: null,
    corpus_en: null,
    corpus_total: null,
    corpus_years: null,
    yearly_cycle_rate: 0.02,
  };
  vi.spyOn(api, "roadmap").mockResolvedValue([
    row,
    { ...row, track_id: "b", name_en: "Rabbi Jacob", units_remaining: 99, projected_finish: null },
  ]);
  render(
    <Provider store={createStore()}>
      <MemoryRouter>
        <RoadmapScreen />
      </MemoryRouter>
    </Provider>,
  );
  await screen.findByText("2026-12-01");
  await userEvent.click(screen.getByRole("button", { name: "Remaining" }));
  expect(screen.getAllByRole("row")[1]?.textContent).toContain("Rabbi Jacob");
});
