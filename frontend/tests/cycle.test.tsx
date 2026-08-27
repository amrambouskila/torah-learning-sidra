import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/api/endpoints";
import { CompressedRail } from "@/components/CompressedRail";
import { TrackScreen } from "@/screens/TrackScreen";
import { createStore } from "@/stores/store";
import { inCycle } from "@/utils/inCycle";
import { percentDone } from "@/utils/percentDone";

import { GEMARA, track } from "./fixtures";

/** The Chumash midway through its second turn: 378 in a cycle, standing at aliyah 7 of the next. */
const SECOND_TURN = track({
  ...GEMARA,
  name_en: "Chumash",
  total: 378,
  cycle_length: 378,
  cycle_index: 2,
  reachable_to: 763,
  actual_ordinal: 385,
  debt: 0,
  is_behind: false,
  is_finished: false,
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("a track that repeats", () => {
  it("folds a position into the turn it belongs to", () => {
    expect(inCycle(SECOND_TURN, 385)).toBe(7);
    expect(inCycle(SECOND_TURN, 378)).toBe(378);
    expect(inCycle(SECOND_TURN, 379)).toBe(1);
  });

  it("leaves a track that runs once alone", () => {
    expect(inCycle(GEMARA, 54)).toBe(54);
  });

  it("measures progress through the current turn, not since the beginning of time", () => {
    // 385/378 would be 102% and climbing forever.
    expect(percentDone(SECOND_TURN)).toBe(2);
  });

  it("reads its position as a place in the cycle rather than a running count", () => {
    render(
      <Provider store={createStore()}>
        <MemoryRouter>
          <CompressedRail track={SECOND_TURN} />
        </MemoryRouter>
      </Provider>,
    );
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/^7 of 378/);
  });
});


describe("the Track screen on a second turn", () => {
  it("counts the position inside the turn and says which turn it is", async () => {
    vi.spyOn(api, "track").mockResolvedValue({
      track: { ...SECOND_TURN, id: "t-gemara" },
      rail: [],
      rail_from: 0,
      rail_to: 0,
    });
    vi.spyOn(api, "rail").mockResolvedValue([]);
    render(
      <Provider store={createStore()}>
        <MemoryRouter initialEntries={["/tracks/t-gemara"]}>
          <Routes>
            <Route path="/tracks/:trackId" element={<TrackScreen />} />
          </Routes>
        </MemoryRouter>
      </Provider>,
    );

    const progress = (await screen.findByText("Progress")).parentElement as HTMLElement;
    expect(progress.textContent).toContain("7");
    expect(progress.textContent).toContain("378");
    expect(progress.textContent).toContain("time 2 round");
    // 385 of 378 would read 102% and climb forever.
    expect(progress.textContent).not.toContain("385");
  });
});
