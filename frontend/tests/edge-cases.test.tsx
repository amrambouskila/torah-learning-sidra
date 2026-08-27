/** The defensive branches: an aborted request, a pinned day on every loader, a typed-in ordinal. */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/api/endpoints";
import { AdvanceDialog } from "@/components/AdvanceDialog";
import { CompressedRail } from "@/components/CompressedRail";
import { ToastStack } from "@/components/ToastStack";
import { ChavrusasScreen } from "@/screens/ChavrusasScreen";
import { RoadmapScreen } from "@/screens/RoadmapScreen";
import { TodayScreen } from "@/screens/TodayScreen";
import { TrackScreen } from "@/screens/TrackScreen";
import { loadAlignment } from "@/stores/alignmentSlice";
import { loadChavrusas } from "@/stores/chavrusasSlice";
import { loadRoadmap } from "@/stores/roadmapSlice";
import { createStore } from "@/stores/store";

import { GEMARA, LIKUTEI, today, track } from "./fixtures";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("an aborted request", () => {
  it("reports itself rather than leaving the screen blank", async () => {
    // A thunk cancelled mid-flight rejects with no payload at all, only an error name.
    vi.spyOn(api, "roadmap").mockReturnValue(new Promise(() => undefined));
    const store = createStore();
    const pending = store.dispatch(loadRoadmap(undefined));
    pending.abort();
    await pending;
    expect(store.getState().roadmap.status).toBe("failed");
    expect(store.getState().roadmap.error).not.toBe("");
    expect(store.getState().roadmap.isConflict).toBe(false);
  });
});

describe("pinning a day", () => {
  it("reaches every loader that takes one", async () => {
    const chavrusas = vi.spyOn(api, "chavrusas").mockResolvedValue([]);
    const store = createStore();
    await store.dispatch(loadChavrusas("2026-08-25"));
    expect(chavrusas).toHaveBeenCalledWith({ on: "2026-08-25" });
    await store.dispatch(loadChavrusas(undefined));
    expect(chavrusas).toHaveBeenCalledWith({});
  });

  it("is not a thing the alignment endpoint takes", async () => {
    const alignment = vi.spyOn(api, "alignment").mockResolvedValue([]);
    const store = createStore();
    await store.dispatch(loadAlignment("t1"));
    expect(alignment).toHaveBeenCalledWith("t1");
  });
});

describe("CompressedRail", () => {
  it("describes itself without a scheduled marker", () => {
    render(<CompressedRail track={track({ scheduled_at: null })} />);
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "120 of 380");
  });

  it("describes both markers when it has them", () => {
    render(<CompressedRail track={track()} />);
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "120 of 380, scheduled 123");
  });

  it("survives a track with nothing in it", () => {
    render(<CompressedRail track={track({ total: 0, actual_ordinal: 0, scheduled_at: null })} />);
    expect(screen.getByRole("img")).toBeInTheDocument();
  });
});

function unit(ordinal: number, sefer: string, ref: string, labelEn: string) {
  return {
    ordinal,
    ref,
    work_title_en: sefer,
    work_title_he: `he-${sefer}`,
    label_en: labelEn,
    label_he: "מ״ה",
    sefaria_url: null,
    is_actual: false,
    is_scheduled: false,
  };
}

function stubAhead() {
  return vi.spyOn(api, "rail").mockImplementation((_id, from, to) =>
    Promise.resolve(
      Array.from({ length: to - from + 1 }, (_, index) => ({
        ordinal: from + index,
        ref: `Jeremiah ${String(from + index)}`,
        work_title_en: "Jeremiah",
        work_title_he: "he-Jeremiah",
        label_en: String(from + index),
        label_he: "מ״ה",
        sefaria_url: null,
        is_actual: false,
        is_scheduled: false,
      })),
    ),
  );
}

describe("AdvanceDialog", () => {
  it("never shows an ordinal — only the addresses he recognises", async () => {
    // The whole point: he knows he finished 5:7, not that 5:7 is unit 289.
    stubAhead();
    render(<AdvanceDialog track={GEMARA} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    const picker = await screen.findByRole("combobox");
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
    // The list now opens twenty units behind him, but it still stands on the next one.
    expect(picker).toHaveValue("55");
    expect(within(picker).getByRole("option", { name: /^55 · / })).toBeInTheDocument();
    expect(screen.getByText(/now at Avodah Zarah 28b/)).toBeInTheDocument();
  });

  it("offers the units behind him too, in a group that says so", async () => {
    // Without the split, a unit he has already passed would read exactly like one he has not,
    // and picking it means something entirely different.
    stubAhead();
    render(<AdvanceDialog track={GEMARA} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    const picker = await screen.findByRole("combobox");
    expect(within(picker).getByRole("group", { name: /^Behind — / })).toBeInTheDocument();
    expect(within(picker).getByRole("option", { name: /^34 · / })).toBeInTheDocument();
  });

  it("relabels itself and names the cost when the choice is behind him", async () => {
    stubAhead();
    const onConfirm = vi.fn();
    render(<AdvanceDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);
    await userEvent.selectOptions(await screen.findByRole("combobox"), "50");

    expect(screen.getByText(/Correcting to Jeremiah 50/)).toBeInTheDocument();
    expect(screen.getByText(/4 amudim behind where you are/)).toBeInTheDocument();
    expect(screen.getByText(/no undo/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Correct position" }));
    expect(onConfirm).toHaveBeenCalledWith({ toOrdinal: 50 }, "50", undefined);
  });

  it("offers the units in front of him and sends the one he picks", async () => {
    stubAhead();
    const onConfirm = vi.fn();
    render(<AdvanceDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);
    await userEvent.selectOptions(await screen.findByRole("combobox"), "57");
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(onConfirm).toHaveBeenCalledWith({ toOrdinal: 57 }, "57", undefined);
  });

  it("reaches far past a single sitting", async () => {
    // "what if i learn more than 8 units uknow" — the list runs to the end of the track here,
    // and the rail is asked for the whole span in one go.
    const spy = stubAhead();
    render(<AdvanceDialog track={GEMARA} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    const picker = await screen.findByRole("combobox");
    // Twenty behind him through the end of the track, in one span.
    expect(spy).toHaveBeenCalledWith(GEMARA.id, 34, GEMARA.total);
    expect(within(picker).getAllByRole("option")).toHaveLength(GEMARA.total - 33);
  });

  it("keeps a hand-typed reference when it is beyond the list", async () => {
    stubAhead();
    render(<AdvanceDialog track={GEMARA} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    const picker = await screen.findByRole("combobox");
    await userEvent.clear(screen.getByLabelText("Or type where you stopped"));
    await userEvent.type(screen.getByLabelText("Or type where you stopped"), "Berakhot 2a");
    expect(picker).toHaveValue("");
    expect(within(picker).getByRole("option", { name: "Somewhere further on" })).toBeInTheDocument();
  });

  it("groups the options by sefer, because the address repeats in each one", async () => {
    // Neviim runs to Jeremiah 52 and starts over at Ezekiel 1. Two options read "1"; only the
    // sefer tells them apart, and the ordinal is what actually travels.
    vi.spyOn(api, "rail").mockResolvedValue([
      unit(55, "Jeremiah", "Jeremiah 52", "52"),
      unit(56, "Ezekiel", "Ezekiel 1", "1"),
      unit(57, "Ezekiel", "Ezekiel 2", "2"),
    ]);
    const onConfirm = vi.fn();
    render(<AdvanceDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);
    const picker = await screen.findByRole("combobox");
    expect([...picker.querySelectorAll("optgroup")].map((group) => group.label)).toEqual([
      "Jeremiah",
      "Ezekiel",
    ]);
    await userEvent.selectOptions(picker, "56");
    // The closed select reads only "1", which is also Jeremiah's first perek. The line beneath
    // it is what makes the choice unambiguous before it is recorded.
    expect(screen.getByText("Recording Ezekiel 1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(onConfirm).toHaveBeenCalledWith({ toOrdinal: 56 }, "1", undefined);
  });

  it("names an aliyah by its ref, since every parsha has a Chamishi", async () => {
    vi.spyOn(api, "rail").mockResolvedValue([
      unit(55, "Parashat HaShavua", "Deuteronomy 27:11-28:6", "Chamishi"),
    ]);
    const onConfirm = vi.fn();
    render(<AdvanceDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);
    const picker = await screen.findByRole("combobox");
    expect(within(picker).getByRole("option")).toHaveAccessibleName(/^Deuteronomy 27:11-28:6 · /);
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(onConfirm).toHaveBeenCalledWith({ toOrdinal: 55 }, "Deuteronomy 27:11-28:6", undefined);
  });

  it("takes a reference typed by hand", async () => {
    stubAhead();
    const onConfirm = vi.fn();
    render(<AdvanceDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);
    const field = await screen.findByLabelText("Or type where you stopped");
    await userEvent.clear(field);
    expect(screen.queryByText(/^Recording /)).not.toBeInTheDocument();
    await userEvent.type(field, "38b");
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(onConfirm).toHaveBeenCalledWith({ toRef: "38b" }, "38b", undefined);
  });

  it("offers to catch up when the scheduled unit is in reach", async () => {
    stubAhead();
    const onConfirm = vi.fn();
    render(
      <AdvanceDialog
        track={track({ ...GEMARA, actual_ordinal: 54, scheduled_at: { ...GEMARA.scheduled_at!, corpus_ordinal: 60 } })}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(await screen.findByRole("button", { name: /Catch up/ }));
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(onConfirm).toHaveBeenCalledWith({ toOrdinal: 60 }, "60", undefined);
  });

  it("treats whitespace as no note", async () => {
    stubAhead();
    const onConfirm = vi.fn();
    render(<AdvanceDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);
    await screen.findByRole("combobox");
    await userEvent.type(screen.getByLabelText("Note (optional)"), "   ");
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(onConfirm).toHaveBeenCalledWith({ toOrdinal: 55 }, "55", undefined);
  });

  it("still works when the unit list cannot be fetched", async () => {
    // The list is a convenience; the field is the guarantee.
    vi.spyOn(api, "rail").mockRejectedValue(new Error("no rail"));
    const onConfirm = vi.fn();
    render(<AdvanceDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);
    const field = screen.getByLabelText("Or type where you stopped");
    await userEvent.type(field, "38b");
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(onConfirm).toHaveBeenCalledWith({ toRef: "38b" }, "38b", undefined);
  });

  it("refuses to record nothing", async () => {
    vi.spyOn(api, "rail").mockResolvedValue([]);
    render(<AdvanceDialog track={GEMARA} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Record" })).toBeDisabled();
    });
  });

  it("opens a sefer never opened at its first unit", async () => {
    // Nothing to report yet: no position behind him, no scheduled unit ahead of him.
    stubAhead();
    const onConfirm = vi.fn();
    render(
      <AdvanceDialog
        track={track({ ...GEMARA, actual_ordinal: 0, at: null, scheduled_at: null })}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    expect(await screen.findByRole("combobox")).toHaveValue("1");
    expect(screen.queryByRole("button", { name: /Catch up/ })).not.toBeInTheDocument();
    expect(screen.getByText("Gemara")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(onConfirm).toHaveBeenCalledWith({ toOrdinal: 1 }, "1", undefined);
  });

  it("still offers the units behind him on a finished track", async () => {
    // There is nothing left to advance to, but a finished track is exactly where a mistyped last
    // unit needs correcting, so the window behind him is the whole point of asking at all.
    const spy = stubAhead();
    render(
      <AdvanceDialog
        track={track({ ...GEMARA, actual_ordinal: GEMARA.total })}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith(GEMARA.id, GEMARA.total - 20, GEMARA.total);
    });
  });
});

describe("a position that resolves to nothing", () => {
  it("falls back to the ordinal in the advance toast", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today({ daily: [GEMARA], shabbat: [], chavrusa: [] }));
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: "a1",
      from_ordinal: 54,
      to_ordinal: 55,
      resolved_ordinal: 55,
      unit_count: 1,
      was_replay: false,
      track: track({ ...GEMARA, at: null }),
    });
    render(
      <Provider store={createStore()}>
        <MemoryRouter>
          <TodayScreen />
          <ToastStack />
        </MemoryRouter>
      </Provider>,
    );
    stubAhead();
    await userEvent.click(await screen.findByRole("button", { name: "Advance" }));
    await userEvent.selectOptions(await screen.findByRole("combobox"), "55");
    await userEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(await screen.findByText(/advanced to/)).toBeInTheDocument();
  });

  it("falls back to the ordinal on the Track screen too", async () => {
    // Node 1 sits behind the marker at 54, so this is a correction now rather than an advance --
    // and the toast it answers with has the same null-position fallback to prove.
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    vi.spyOn(api, "rail").mockResolvedValue([
      {
        ordinal: 1,
        ref: "Avodah Zarah 2a",
        work_title_en: "Jeremiah",
        work_title_he: "he-Jeremiah",
        label_en: "amud 1",
        label_he: "ב׳ ע״א",
        sefaria_url: null,
        is_actual: false,
        is_scheduled: false,
      },
    ]);
    vi.spyOn(api, "correctPosition").mockResolvedValue({
      from_ordinal: 54,
      to_ordinal: 1,
      removed_units: 53,
      removed_advances: 1,
      moved: true,
      track: track({ ...GEMARA, at: null }),
    });
    render(
      <Provider store={createStore()}>
        <MemoryRouter initialEntries={["/tracks/t-gemara"]}>
          <Routes>
            <Route path="/tracks/:trackId" element={<TrackScreen />} />
          </Routes>
        </MemoryRouter>
      </Provider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: /amud 1:/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Correct position" }));
    await waitFor(() => {
      expect(api.correctPosition).toHaveBeenCalledWith("t-gemara", { toOrdinal: 1 }, true);
    });
  });
});

describe("ChavrusasScreen", () => {
  it("falls back to the track name when a track has no position", async () => {
    vi.spyOn(api, "chavrusas").mockResolvedValue([
      {
        id: "c1",
        name: "Nesher",
        notes: null,
        days_stale: null,
        tracks: [track({ ...LIKUTEI, at: null })],
        sessions: [],
      },
    ]);
    render(
      <Provider store={createStore()}>
        <MemoryRouter>
          <ChavrusasScreen />
        </MemoryRouter>
      </Provider>,
    );
    expect(await screen.findByText("Likutei Sichot")).toBeInTheDocument();
  });

  it("renders a session with no note", async () => {
    vi.spyOn(api, "chavrusas").mockResolvedValue([
      {
        id: "c1",
        name: "Nesher",
        notes: null,
        days_stale: 2,
        tracks: [],
        sessions: [
          {
            occurred_on: "2026-08-23",
            hebrew_date: "י׳ באלול",
            from_ordinal: 1,
            to_ordinal: 2,
            unit_count: 1,
            note: null,
          },
        ],
      },
    ]);
    render(
      <Provider store={createStore()}>
        <MemoryRouter>
          <ChavrusasScreen />
        </MemoryRouter>
      </Provider>,
    );
    expect(await screen.findByText("2026-08-23")).toBeInTheDocument();
  });
});

describe("RoadmapScreen", () => {
  it("puts an undated track last whichever order it arrives in", async () => {
    const dated = {
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
    const undated = { ...dated, track_id: "b", name_en: "Rabbi Jacob", projected_finish: null };
    for (const rows of [
      [dated, undated],
      [undated, dated],
    ]) {
      vi.spyOn(api, "roadmap").mockResolvedValue(rows);
      const { unmount } = render(
        <Provider store={createStore()}>
          <MemoryRouter>
            <RoadmapScreen />
          </MemoryRouter>
        </Provider>,
      );
      await screen.findByText("2026-12-01");
      const body = screen.getAllByRole("row").slice(1);
      expect(within(body[0] as HTMLElement).getByText("Gemara")).toBeInTheDocument();
      unmount();
    }
  });

  it("keeps two undated tracks in a stable order", async () => {
    vi.spyOn(api, "roadmap").mockResolvedValue([
      {
        track_id: "a",
        name_en: "Rabbi Jacob",
        name_he: "יעקב",
        total: 10,
        actual_ordinal: 1,
        units_remaining: 9,
        rate_per_day: 0,
        debt: 0,
        projected_finish: null,
        work_ref_title: null,
        corpus_en: null,
        corpus_total: null,
        corpus_years: null,
        yearly_cycle_rate: 0.02,
      },
      {
        track_id: "b",
        name_en: "David Cohen",
        name_he: "דוד",
        total: 10,
        actual_ordinal: 1,
        units_remaining: 9,
        rate_per_day: 0,
        debt: 0,
        projected_finish: null,
        work_ref_title: null,
        corpus_en: null,
        corpus_total: null,
        corpus_years: null,
        yearly_cycle_rate: 0.02,
      },
    ]);
    render(
      <Provider store={createStore()}>
        <MemoryRouter>
          <RoadmapScreen />
        </MemoryRouter>
      </Provider>,
    );
    expect(await screen.findAllByText("no schedule")).toHaveLength(2);
  });
});
