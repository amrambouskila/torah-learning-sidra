import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { TodayScreen } from "@/screens/TodayScreen";
import { ToastStack } from "@/components/ToastStack";
import { createStore } from "@/stores/store";

import { GEMARA, today, track } from "../fixtures";
function stubAhead(): void {
  vi.spyOn(api, "rail").mockImplementation((_id, from, to) =>
    Promise.resolve(
      Array.from({ length: Math.max(0, to - from + 1) }, (_, index) => ({
        ordinal: from + index,
        ref: `Avodah Zarah ${String(from + index)}`,
        work_title_en: "Jeremiah",
        work_title_he: "he-Jeremiah",
        label_en: String(from + index),
        label_he: "כ״ט",
        sefaria_url: null,
        is_actual: false,
        is_scheduled: false,
      })),
    ),
  );
}

function renderToday() {
  const store = createStore();
  render(
    <Provider store={store}>
      <MemoryRouter>
        <TodayScreen />
        <ToastStack />
      </MemoryRouter>
    </Provider>,
  );
  return store;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TodayScreen", () => {
  it("opens with the most-behind track first", async () => {
    // The spec's opening line: Avoda Zara twenty amudim behind, then Yirmiyahu three perakim.
    vi.spyOn(api, "today").mockResolvedValue(today());
    renderToday();

    const daily = await screen.findByRole("heading", { name: /Daily/ });
    const list = daily.parentElement?.querySelector(".group__list");
    const names = [...(list?.querySelectorAll(".card") ?? [])].map(
      (card) => card.querySelector(".gloss")?.textContent,
    );
    expect(names).toEqual(["Gemara", "Neviim", "Chumash"]);
  });

  it("names the units in the debt badge", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    renderToday();
    expect(await screen.findByText("amudim behind")).toBeInTheDocument();
    expect(screen.getByText("perakim behind")).toBeInTheDocument();
  });

  it("shows the Hebrew date and the parsha", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    renderToday();
    expect(await screen.findByText("י״ב בֶּאֱלוּל תשפ״ו")).toBeInTheDocument();
    expect(screen.getByText("כי תבוא")).toBeInTheDocument();
  });

  it("groups the three fixed categories", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    renderToday();
    for (const name of ["Daily", "Shabbat", "Chavrusa"]) {
      expect(await screen.findByRole("heading", { name: new RegExp(name) })).toBeInTheDocument();
    }
  });

  it("shows a chavrusa's staleness rather than a debt", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    renderToday();
    expect(await screen.findByText("weeks since")).toBeInTheDocument();
  });

  it("counts down a track that has not started", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    renderToday();
    expect(await screen.findByText("weeks away")).toBeInTheDocument();
  });

  it("filters across categories by tag", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    renderToday();
    await screen.findByText("amudim behind");

    await userEvent.click(screen.getByRole("button", { name: "parsha" }));
    await waitFor(() => {
      expect(screen.queryByText("Gemara")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Chumash")).toBeInTheDocument();
    expect(screen.getByText("Likutei Sichot")).toBeInTheDocument();
  });

  it("clears the filter when the same tag is clicked again", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    renderToday();
    await screen.findByText("amudim behind");
    const pill = screen.getByRole("button", { name: "parsha" });
    await userEvent.click(pill);
    await userEvent.click(pill);
    expect(await screen.findByText("Gemara")).toBeInTheDocument();
  });

  it("records an advance and says so", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    const moved = track({ ...GEMARA, actual_ordinal: 74, debt: 0, is_behind: false });
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: "a1",
      from_ordinal: 54,
      to_ordinal: 74,
      resolved_ordinal: 74,
      unit_count: 20,
      was_replay: false,
      track: moved,
    });
    renderToday();

    stubAhead();
    const card = (await screen.findByText("Gemara")).closest(".card");
    await userEvent.click(within(card as HTMLElement).getByRole("button", { name: "Advance" }));

    const dialog = await screen.findByRole("dialog");
    await userEvent.selectOptions(await within(dialog).findByRole("combobox"), "74");
    await userEvent.click(within(dialog).getByRole("button", { name: "Record" }));

    expect(await screen.findByText(/Gemara advanced to/)).toBeInTheDocument();
    expect(api.advance).toHaveBeenCalledWith("t-gemara", { toOrdinal: 74 }, {});
  });

  it("sends the note when one is typed", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: "a1",
      from_ordinal: 54,
      to_ordinal: 55,
      resolved_ordinal: 55,
      unit_count: 1,
      was_replay: false,
      track: GEMARA,
    });
    renderToday();

    stubAhead();
    const card = (await screen.findByText("Gemara")).closest(".card");
    await userEvent.click(within(card as HTMLElement).getByRole("button", { name: "Advance" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByRole("combobox");
    await userEvent.type(within(dialog).getByLabelText("Note (optional)"), "finished the sugya");
    await userEvent.click(within(dialog).getByRole("button", { name: "Record" }));

    expect(api.advance).toHaveBeenCalledWith("t-gemara", { toOrdinal: 55 }, { note: "finished the sugya" });
  });

  it("says plainly when an advance was a replay", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: null,
      from_ordinal: 54,
      to_ordinal: 54,
      resolved_ordinal: 54,
      unit_count: 0,
      was_replay: true,
      track: GEMARA,
    });
    renderToday();
    stubAhead();
    const card = (await screen.findByText("Gemara")).closest(".card");
    await userEvent.click(within(card as HTMLElement).getByRole("button", { name: "Advance" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByRole("combobox");
    await userEvent.click(within(dialog).getByRole("button", { name: "Record" }));
    expect(await screen.findByText(/was already there/)).toBeInTheDocument();
  });

  it("surfaces a refused advance as a toast", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    vi.spyOn(api, "advance").mockRejectedValue(new ApiError("the track holds 150 units", 422));
    renderToday();
    stubAhead();
    const card = (await screen.findByText("Gemara")).closest(".card");
    await userEvent.click(within(card as HTMLElement).getByRole("button", { name: "Advance" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByRole("combobox");
    await userEvent.click(within(dialog).getByRole("button", { name: "Record" }));
    expect(await screen.findByText("the track holds 150 units")).toBeInTheDocument();
  });

  it("closes the dialog on cancel without advancing", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    const advance = vi.spyOn(api, "advance");
    renderToday();
    const card = (await screen.findByText("Gemara")).closest(".card");
    await userEvent.click(within(card as HTMLElement).getByRole("button", { name: "Advance" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(advance).not.toHaveBeenCalled();
  });

  it("renders a missing calendar as an actionable banner", async () => {
    vi.spyOn(api, "today").mockRejectedValue(
      new ApiError("no calendar snapshot for 2026-08-25; run the calendar command", 409),
    );
    renderToday();
    expect(await screen.findByRole("alert")).toHaveTextContent("run the calendar command");
    expect(screen.getByText("The data is not ready yet")).toBeInTheDocument();
  });

  it("distinguishes a real failure from data that is not ready", async () => {
    vi.spyOn(api, "today").mockRejectedValue(new ApiError("boom", 500));
    renderToday();
    expect(await screen.findByText("That did not work")).toBeInTheDocument();
  });

  it("dismisses a toast when asked", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: "a1",
      from_ordinal: 54,
      to_ordinal: 55,
      resolved_ordinal: 55,
      unit_count: 1,
      was_replay: false,
      track: GEMARA,
    });
    renderToday();
    stubAhead();
    const card = (await screen.findByText("Gemara")).closest(".card");
    await userEvent.click(within(card as HTMLElement).getByRole("button", { name: "Advance" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByRole("combobox");
    await userEvent.click(within(dialog).getByRole("button", { name: "Record" }));
    await screen.findByText(/advanced to/);
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() => {
      expect(screen.queryByText(/advanced to/)).not.toBeInTheDocument();
    });
  });

  it("offers no advance on a finished track", async () => {
    vi.spyOn(api, "today").mockResolvedValue(
      today({ daily: [track({ is_finished: true, up_next: null, debt: 0, is_behind: false })], shabbat: [], chavrusa: [] }),
    );
    renderToday();
    expect(await screen.findByRole("button", { name: "Finished" })).toBeDisabled();
  });
});
