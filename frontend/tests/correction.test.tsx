/**
 * Going backwards: correcting where a track actually stands.
 *
 * Two routes in, because a place can be named two ways. A unit picked off the list carries its
 * ordinal, so the dialog settles the direction itself. A reference typed by hand does not — it
 * only reveals which way it points once the server has resolved it, so a replay that landed behind
 * him becomes an offer to correct rather than a shrug.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { CorrectionPrompt } from "@/components/CorrectionPrompt";
import { ToastStack } from "@/components/ToastStack";
import { TodayScreen } from "@/screens/TodayScreen";
import { createStore } from "@/stores/store";
import { correctSchedule, loadTracks } from "@/stores/tracksSlice";

import { GEMARA, today, track } from "./fixtures";

function stubSpan(): void {
  vi.spyOn(api, "rail").mockImplementation((_id, from, to) =>
    Promise.resolve(
      Array.from({ length: Math.max(0, to - from + 1) }, (_, index) => ({
        ordinal: from + index,
        ref: `Avodah Zarah ${String(from + index)}`,
        work_title_en: "Avodah Zarah",
        work_title_he: "עבודה זרה",
        label_en: String(from + index),
        label_he: "כ״ט",
        sefaria_url: null,
        is_actual: false,
        is_scheduled: false,
      })),
    ),
  );
}

function renderToday(): void {
  render(
    <Provider store={createStore()}>
      <MemoryRouter>
        <TodayScreen />
        <ToastStack />
      </MemoryRouter>
    </Provider>,
  );
}

async function openAdvance(): Promise<void> {
  const cards = await screen.findAllByRole("button", { name: /Advance/ });
  const gemara = cards[0];
  if (gemara === undefined) throw new Error("no advance button");
  await userEvent.click(gemara);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("a reference typed behind him", () => {
  it("offers to correct rather than shrugging that he was already there", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [GEMARA], shabbat: [], chavrusa: [] }));
    stubSpan();
    // The server resolved it to 50; he stands at 54. Only the response can say that.
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: null,
      resolved_ordinal: 50,
      from_ordinal: 54,
      to_ordinal: 54,
      unit_count: 0,
      was_replay: true,
      track: GEMARA,
    });
    vi.spyOn(api, "correctPosition").mockResolvedValue({
      from_ordinal: 54,
      to_ordinal: 50,
      removed_units: 4,
      removed_advances: 1,
      moved: true,
      track: track({ ...GEMARA, actual_ordinal: 50 }),
    });
    renderToday();
    await openAdvance();

    const field = await screen.findByLabelText("Or type where you stopped");
    await userEvent.clear(field);
    await userEvent.type(field, "36a");
    await userEvent.click(screen.getByRole("button", { name: "Record" }));

    expect(await screen.findByText(/4 amudim behind where you are/)).toBeInTheDocument();
    expect(screen.queryByText(/was already there/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Correct position" }));
    await waitFor(() => {
      expect(api.correctPosition).toHaveBeenCalledWith("t-gemara", { toOrdinal: 50 }, true);
    });
    expect(await screen.findByText(/back to .* — 4 removed/i)).toBeInTheDocument();
  });

  it("still says he was already there when the reference is where he stands", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [GEMARA], shabbat: [], chavrusa: [] }));
    stubSpan();
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: null,
      resolved_ordinal: 54,
      from_ordinal: 54,
      to_ordinal: 54,
      unit_count: 0,
      was_replay: true,
      track: GEMARA,
    });
    renderToday();
    await openAdvance();

    const field = await screen.findByLabelText("Or type where you stopped");
    await userEvent.clear(field);
    await userEvent.type(field, "28b");
    await userEvent.click(screen.getByRole("button", { name: "Record" }));

    expect(await screen.findByText(/was already there/)).toBeInTheDocument();
  });

  it("lets him back out of the offer", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [GEMARA], shabbat: [], chavrusa: [] }));
    stubSpan();
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: null,
      resolved_ordinal: 50,
      from_ordinal: 54,
      to_ordinal: 54,
      unit_count: 0,
      was_replay: true,
      track: GEMARA,
    });
    vi.spyOn(api, "correctPosition");
    renderToday();
    await openAdvance();

    const field = await screen.findByLabelText("Or type where you stopped");
    await userEvent.clear(field);
    await userEvent.type(field, "36a");
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(api.correctPosition).not.toHaveBeenCalled();
    expect(screen.queryByText(/behind where you are/)).not.toBeInTheDocument();
  });
});

describe("a unit picked behind him", () => {
  it("goes straight to the correction without posting an advance first", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [GEMARA], shabbat: [], chavrusa: [] }));
    stubSpan();
    vi.spyOn(api, "advance");
    vi.spyOn(api, "correctPosition").mockResolvedValue({
      from_ordinal: 54,
      to_ordinal: 40,
      removed_units: 14,
      removed_advances: 2,
      moved: true,
      track: track({ ...GEMARA, actual_ordinal: 40 }),
    });
    renderToday();
    await openAdvance();

    await userEvent.selectOptions(await screen.findByRole("combobox"), "40");
    await userEvent.click(screen.getByRole("button", { name: "Correct position" }));

    expect(api.advance).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(api.correctPosition).toHaveBeenCalledWith("t-gemara", { toOrdinal: 40 }, true);
    });
  });

  it("surfaces a refusal from the server", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [GEMARA], shabbat: [], chavrusa: [] }));
    stubSpan();
    vi.spyOn(api, "correctPosition").mockRejectedValue(new ApiError("there is no undo", 422));
    renderToday();
    await openAdvance();

    await userEvent.selectOptions(await screen.findByRole("combobox"), "40");
    await userEvent.click(screen.getByRole("button", { name: "Correct position" }));

    // The server's own sentence, not a generic failure: it is the only useful part.
    expect(await screen.findByText("there is no undo")).toBeInTheDocument();
  });
});

describe("a corrected track with nothing left to name", () => {
  it("falls back to the label in the Today toast", async () => {
    // Corrected all the way back to unopened: there is no position to read out.
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [GEMARA], shabbat: [], chavrusa: [] }));
    stubSpan();
    vi.spyOn(api, "correctPosition").mockResolvedValue({
      from_ordinal: 54,
      to_ordinal: 40,
      removed_units: 14,
      removed_advances: 2,
      moved: true,
      track: track({ ...GEMARA, actual_ordinal: 0, at: null }),
    });
    renderToday();
    await openAdvance();

    await userEvent.selectOptions(await screen.findByRole("combobox"), "40");
    await userEvent.click(screen.getByRole("button", { name: "Correct position" }));

    expect(await screen.findByText(/back to 40 — 14 removed/i)).toBeInTheDocument();
  });
});

describe("CorrectionPrompt", () => {
  it("falls back to the track name when it has no position to show", () => {
    // A track corrected all the way back to nothing has no `at` to name.
    render(
      <CorrectionPrompt
        track={track({ ...GEMARA, at: null })}
        toOrdinal={50}
        label="36a"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText(/now at Gemara/)).toBeInTheDocument();
    expect(screen.getByText(/Correcting to 36a/)).toBeInTheDocument();
  });
});

describe("the schedule slice", () => {
  it("leaves other rows alone when one track's schedule is corrected", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([GEMARA, track({ ...GEMARA, id: "t-other" })]);
    vi.spyOn(api, "correctSchedule").mockResolvedValue(track({ ...GEMARA, debt: 0 }));
    const store = createStore();
    await store.dispatch(loadTracks(undefined));
    await store.dispatch(correctSchedule({ trackId: "t-gemara", correction: { toOrdinal: 54 } }));

    expect(store.getState().tracks.data[1]?.id).toBe("t-other");
    expect(store.getState().tracks.data[1]?.debt).toBe(20);
  });
});
