import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { PaceScreen } from "@/screens/PaceScreen";
import { createStore } from "@/stores/store";
import { loadPace } from "@/stores/paceSlice";
import type { PaceRow } from "@/types/PaceRow";

const BAVLI: PaceRow = {
  row_id: "bavli.amud",
  scope_en: "Talmud Bavli",
  unit_singular: "amud",
  unit_plural: "amudim",
  total: 5349,
  per_day_for_horizon: 14.65,
  years_at_rate: 14.65,
  note: null,
};

const DAF: PaceRow = {
  ...BAVLI,
  row_id: "bavli.daf",
  unit_singular: "daf",
  unit_plural: "daf",
  total: 2684,
  per_day_for_horizon: 7.35,
  years_at_rate: 7.35,
  note: "2,684 daf carry text in Sefaria. The traditional count of 2,711 includes daf that hold no Gemara.",
};

function renderPace() {
  render(
    <Provider store={createStore()}>
      <MemoryRouter>
        <PaceScreen />
      </MemoryRouter>
    </Provider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("PaceScreen", () => {
  it("shows the whole catalog as cycles", async () => {
    vi.spyOn(api, "pace").mockResolvedValue([BAVLI, DAF]);
    renderPace();
    expect(await screen.findByText("5,349")).toBeInTheDocument();
    expect(screen.getByText("2,684")).toBeInTheDocument();
  });

  it("lists the same body twice at different granularities", async () => {
    // Something a roadmap structurally could not do, and the clearest signal this is not one.
    vi.spyOn(api, "pace").mockResolvedValue([BAVLI, DAF]);
    renderPace();
    await screen.findByText("5,349");
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows.map((row) => within(row).getByRole("rowheader").textContent)).toEqual([
      "Talmud Bavli",
      "Talmud Bavli",
    ]);
    expect(screen.getByText("amudim")).toBeInTheDocument();
    expect(screen.getByText("daf")).toBeInTheDocument();
  });

  it("says plainly that it is not the plan", async () => {
    vi.spyOn(api, "pace").mockResolvedValue([BAVLI]);
    renderPace();
    expect(await screen.findByText(/None of this is your plan/)).toBeInTheDocument();
  });

  it("renders no date anywhere, only durations", async () => {
    vi.spyOn(api, "pace").mockResolvedValue([BAVLI, DAF]);
    renderPace();
    await screen.findByText("5,349");
    expect(document.body.textContent).not.toMatch(/\d{4}-\d{2}-\d{2}/);
  });

  it("asks the server again when the horizon changes", async () => {
    const spy = vi.spyOn(api, "pace").mockResolvedValue([BAVLI]);
    renderPace();
    await screen.findByText("5,349");
    await userEvent.click(screen.getByRole("button", { name: "7 years" }));
    expect(spy).toHaveBeenLastCalledWith(7, 1);
  });

  it("asks the server again when the rate changes", async () => {
    const spy = vi.spyOn(api, "pace").mockResolvedValue([BAVLI]);
    renderPace();
    await screen.findByText("5,349");
    await userEvent.click(screen.getByRole("button", { name: "3 a day" }));
    expect(spy).toHaveBeenLastCalledWith(1, 3);
  });

  it("echoes the chosen knobs into the column headings", async () => {
    vi.spyOn(api, "pace").mockResolvedValue([BAVLI]);
    renderPace();
    await screen.findByText("5,349");
    expect(screen.getByRole("columnheader", { name: /A day, for a year/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "18 years" }));
    expect(screen.getByRole("columnheader", { name: /A day, for 18 years/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "2 a day" }));
    expect(screen.getByRole("columnheader", { name: /Years, at 2 a day/ })).toBeInTheDocument();
  });

  it("surfaces a caveat rather than quietly disagreeing with the tradition", async () => {
    vi.spyOn(api, "pace").mockResolvedValue([BAVLI, DAF]);
    renderPace();
    expect(await screen.findByText(/2,711/)).toBeInTheDocument();
  });

  it("shows no notes list when nothing is caveated", async () => {
    vi.spyOn(api, "pace").mockResolvedValue([BAVLI]);
    renderPace();
    await screen.findByText("5,349");
    expect(screen.queryByText(/2,711/)).not.toBeInTheDocument();
  });

  it("surfaces a failure", async () => {
    vi.spyOn(api, "pace").mockRejectedValue(new ApiError("run 'sidra-db seed'", 409));
    renderPace();
    expect(await screen.findByRole("alert")).toHaveTextContent("sidra-db seed");
  });
});

describe("the pace endpoint", () => {
  it("passes both knobs through", async () => {
    const spy = vi.spyOn(api, "pace").mockResolvedValue([]);
    const store = createStore();
    await store.dispatch(loadPace({ years: 3, perDay: 5 }));
    expect(spy).toHaveBeenCalledWith(3, 5);
  });

  it("keeps the backend's sentence on failure", async () => {
    vi.spyOn(api, "pace").mockRejectedValue(new ApiError("the catalog holds no counted work", 409));
    const store = createStore();
    await store.dispatch(loadPace({ years: 1, perDay: 1 }));
    expect(store.getState().pace.error).toMatch(/no counted work/);
    expect(store.getState().pace.isConflict).toBe(true);
  });
});
