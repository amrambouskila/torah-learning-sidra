import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/api/endpoints";
import { RoadmapScreen } from "@/screens/RoadmapScreen";
import { createStore } from "@/stores/store";
import type { RoadmapRow } from "@/types/RoadmapRow";

function row(overrides: Partial<RoadmapRow> = {}): RoadmapRow {
  return {
    track_id: "t-gemara",
    name_en: "Gemara",
    name_he: "גמרא",
    work_ref_title: "Avodah Zarah",
    corpus_en: "Talmud Bavli",
    corpus_total: 5349,
    corpus_years: 14.7,
    total: 150,
    actual_ordinal: 54,
    units_remaining: 96,
    rate_per_day: 1,
    debt: 22,
    projected_finish: "2026-11-30",
    yearly_cycle_rate: 0.41,
    ...overrides,
  };
}

function mount() {
  render(
    <Provider store={createStore()}>
      <MemoryRouter>
        <RoadmapScreen />
      </MemoryRouter>
    </Provider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("a roadmap row that is one work of a longer road", () => {
  it("names the work it is actually projecting", async () => {
    // "Gemara finishes 2026-11-30" overclaims by a factor of thirty-five.
    vi.spyOn(api, "roadmap").mockResolvedValue([row()]);
    mount();
    expect(await screen.findByText("Gemara · Avodah Zarah")).toBeInTheDocument();
  });

  it("gives the whole body as a second, honest scale", async () => {
    vi.spyOn(api, "roadmap").mockResolvedValue([row()]);
    mount();
    expect(await screen.findByText(/all of Talmud Bavli at this pace/)).toBeInTheDocument();
    expect(screen.getByText("14.7")).toBeInTheDocument();
  });

  it("says nothing wider when the track already is the whole body", async () => {
    vi.spyOn(api, "roadmap").mockResolvedValue([
      row({ name_en: "Neviim", work_ref_title: null, corpus_en: null, corpus_total: null, corpus_years: null }),
    ]);
    mount();
    expect(await screen.findByText("Neviim")).toBeInTheDocument();
    expect(screen.queryByText(/at this pace/)).not.toBeInTheDocument();
  });

  it("does not repeat itself when the track is named for its work", async () => {
    vi.spyOn(api, "roadmap").mockResolvedValue([
      row({ name_en: "Avodah Zarah", work_ref_title: "Avodah Zarah" }),
    ]);
    mount();
    expect(await screen.findByText("Avodah Zarah")).toBeInTheDocument();
    expect(screen.queryByText("Avodah Zarah · Avodah Zarah")).not.toBeInTheDocument();
  });
});
