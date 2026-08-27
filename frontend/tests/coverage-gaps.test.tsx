/**
 * The branches the screen tests do not reach on their own: a coloured tag, a Yom Tov day, a
 * failure that arrives with no message at all, and a rail chunk asked for twice.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/api/endpoints";
import { TagPill } from "@/components/TagPill";
import { TrackCard } from "@/components/TrackCard";
import { Rail } from "@/components/Rail";
import { TodayScreen } from "@/screens/TodayScreen";
import { createStore } from "@/stores/store";
import { loadRoadmap } from "@/stores/roadmapSlice";
import { loadToday } from "@/stores/todaySlice";

import { LIKUTEI, today, track } from "./fixtures";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TagPill", () => {
  it("wears its own colour when it has one", () => {
    render(<TagPill name="parsha" color="#8a6d3b" />);
    expect(screen.getByText("parsha")).toHaveStyle({ color: "#8a6d3b" });
  });

  it("wears the default when it has none", () => {
    render(<TagPill name="parsha" color={null} />);
    expect(screen.getByText("parsha")).toBeInTheDocument();
  });

  it("colours a clickable pill too", () => {
    render(<TagPill name="parsha" color="#8a6d3b" onClick={vi.fn()} />);
    expect(screen.getByRole("button", { name: "parsha" })).toHaveStyle({ color: "#8a6d3b" });
  });
});

describe("TrackCard", () => {
  it("falls back to the next unit when nothing has been learned", () => {
    render(
      <MemoryRouter>
        <ul>
          <TrackCard track={LIKUTEI} onAdvance={vi.fn()} onSetStart={vi.fn()} />
        </ul>
      </MemoryRouter>,
    );
    expect(screen.getByText("Likutei Sichot 1")).toBeInTheDocument();
  });

  it("says not started when there is no position at all", () => {
    render(
      <MemoryRouter>
        <ul>
          <TrackCard track={track({ at: null, up_next: null })} onAdvance={vi.fn()} onSetStart={vi.fn()} />
        </ul>
      </MemoryRouter>,
    );
    expect(screen.getByText("not started")).toBeInTheDocument();
  });
});

describe("TodayScreen", () => {
  it("marks a Yom Tov", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ is_yom_tov: true }));
    render(
      <Provider store={createStore()}>
        <MemoryRouter>
          <TodayScreen />
        </MemoryRouter>
      </Provider>,
    );
    expect(await screen.findByText("Yom Tov")).toBeInTheDocument();
  });

  it("renders a day with no parsha without inventing one", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ parsha_en: [], parsha_he: [] }));
    render(
      <Provider store={createStore()}>
        <MemoryRouter>
          <TodayScreen />
        </MemoryRouter>
      </Provider>,
    );
    await screen.findByText("2026-08-25");
    expect(screen.queryByText("כי תבוא")).not.toBeInTheDocument();
  });

  it("shows nothing but a heading before the first response lands", () => {
    vi.spyOn(api, "today").mockReturnValue(new Promise(() => undefined));
    render(
      <Provider store={createStore()}>
        <MemoryRouter>
          <TodayScreen />
        </MemoryRouter>
      </Provider>,
    );
    expect(screen.getByText("Loading the sidra…")).toBeInTheDocument();
  });
});

describe("a failure with nothing to say", () => {
  it("falls back to a sentence of its own", async () => {
    // A thunk can reject with an Error that has an empty message; the screen still needs words.
    vi.spyOn(api, "roadmap").mockRejectedValue(new Error(""));
    const store = createStore();
    await store.dispatch(loadRoadmap(undefined));
    expect(store.getState().roadmap.error).toBe("The request failed.");
  });

  it("passes a pinned day to Today", async () => {
    const spy = vi.spyOn(api, "today").mockResolvedValue(today());
    const store = createStore();
    await store.dispatch(loadToday("2026-08-25"));
    expect(spy).toHaveBeenCalledWith({ on: "2026-08-25" });
  });
});

describe("Rail chunk caching", () => {
  it("asks for a chunk once however often it comes back into view", async () => {
    const spy = vi.spyOn(api, "rail").mockResolvedValue([
      {
        ordinal: 1,
        ref: "Avodah Zarah 2a",
        work_title_en: "Avodah Zarah",
        work_title_he: "עבודה זרה",
        label_en: "amud 1",
        label_he: "ב׳ ע״א",
        sefaria_url: null,
        is_actual: true,
        is_scheduled: false,
      },
    ]);
    const { rerender } = render(
      <Rail trackId="t1" total={50} actual={1} scheduled={null} onSelect={vi.fn()} />,
    );
    await screen.findByRole("button", { name: /amud 1:/ });
    rerender(<Rail trackId="t1" total={50} actual={1} scheduled={null} onSelect={vi.fn()} />);
    await waitFor(() => {
      expect(spy).toHaveBeenCalledTimes(1);
    });
  });
});
