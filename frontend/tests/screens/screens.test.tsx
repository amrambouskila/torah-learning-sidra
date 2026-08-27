import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { ToastStack } from "@/components/ToastStack";
import { AlignmentScreen } from "@/screens/AlignmentScreen";
import { ChavrusasScreen } from "@/screens/ChavrusasScreen";
import { RoadmapScreen } from "@/screens/RoadmapScreen";
import { TagsScreen } from "@/screens/TagsScreen";
import { TrackScreen } from "@/screens/TrackScreen";
import { createStore } from "@/stores/store";
import type { RailUnit } from "@/types/RailUnit";

import { GEMARA, HADAR, LIKUTEI, track } from "../fixtures";

function mount(node: React.ReactNode, path = "/") {
  render(
    <Provider store={createStore()}>
      <MemoryRouter initialEntries={[path]}>
        {node}
        <ToastStack />
      </MemoryRouter>
    </Provider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

// --- Track -----------------------------------------------------------------------------------

function stubRail(): void {
  vi.spyOn(api, "rail").mockImplementation((_id, from, to) => {
    const units: RailUnit[] = [];
    for (let ordinal = from; ordinal <= to; ordinal += 1) {
      units.push({
        ordinal,
        ref: `Avodah Zarah ${String(ordinal)}`,
        work_title_en: "Jeremiah",
        work_title_he: "he-Jeremiah",
        label_en: `amud ${String(ordinal)}`,
        label_he: `דף ${String(ordinal)}`,
        sefaria_url: null,
        is_actual: false,
        is_scheduled: false,
      });
    }
    return Promise.resolve(units);
  });
}

/**
 * Gemara standing at unit 2, so the rail's opening window holds units both behind and ahead of the
 * marker. The real fixture stands at 54, past everything the first window draws.
 */
const EARLY = track({ ...GEMARA, actual_ordinal: 2 });

function mountTrack() {
  mount(
    <Routes>
      <Route path="/tracks/:trackId" element={<TrackScreen />} />
    </Routes>,
    "/tracks/t-gemara",
  );
}

describe("TrackScreen", () => {
  it("shows both markers and the progress", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    mountTrack();

    expect(await screen.findByText("גמרא")).toBeInTheDocument();
    expect(screen.getByText("Avodah Zarah 28b")).toBeInTheDocument();
    expect(screen.getByText("Avodah Zarah 38b")).toBeInTheDocument();
    expect(screen.getByText("36%")).toBeInTheDocument();
    expect(screen.getByText("amudim behind")).toBeInTheDocument();
  });

  it("says plainly when a track has no schedule", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: HADAR, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    mountTrack();
    expect(await screen.findByText("no schedule")).toBeInTheDocument();
  });

  it("says plainly when a finished track has nowhere further to go", async () => {
    const finished = track({ ...LIKUTEI, at: null, up_next: null, is_finished: true });
    vi.spyOn(api, "track").mockResolvedValue({ track: finished, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    mountTrack();
    expect(await screen.findByText("not started")).toBeInTheDocument();
  });

  it("moves the position when a node on the rail is chosen", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: EARLY, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: "a1",
      from_ordinal: 2,
      to_ordinal: 3,
      resolved_ordinal: 3,
      unit_count: 1,
      was_replay: false,
      track: GEMARA,
    });
    mountTrack();
    // Ahead of the marker: a node behind it is a correction, tested below.
    await userEvent.click(await screen.findByRole("button", { name: /amud 3:/ }));
    expect(api.advance).toHaveBeenCalledWith("t-gemara", { toOrdinal: 3 }, {});
    expect(await screen.findByText(/Moved to/)).toBeInTheDocument();
  });

  it("says so when the move was a replay", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: EARLY, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: null,
      from_ordinal: 2,
      to_ordinal: 2,
      resolved_ordinal: 2,
      unit_count: 0,
      was_replay: true,
      track: EARLY,
    });
    mountTrack();
    await userEvent.click(await screen.findByRole("button", { name: /amud 3:/ }));
    expect(await screen.findByText(/Already there/)).toBeInTheDocument();
  });

  it("surfaces a refused move", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: EARLY, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "advance").mockRejectedValue(new ApiError("the track holds 150 units", 422));
    mountTrack();
    await userEvent.click(await screen.findByRole("button", { name: /amud 3:/ }));
    expect(await screen.findByText("the track holds 150 units")).toBeInTheDocument();
  });

  it("names the move itself when the advanced track has no position", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: EARLY, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: "a1",
      from_ordinal: 2,
      to_ordinal: 3,
      resolved_ordinal: 3,
      unit_count: 1,
      was_replay: false,
      track: track({ ...GEMARA, at: null }),
    });
    mountTrack();

    await userEvent.click(await screen.findByRole("button", { name: /amud 3:/ }));
    expect(await screen.findByText(/Moved to the new position/)).toBeInTheDocument();
  });

  it("offers to correct rather than advancing when the node is behind the marker", async () => {
    // The rail already knows the ordinal, so the direction is settled here rather than by posting
    // an advance and reading a replay back -- and going backwards is never done unasked.
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "advance");
    vi.spyOn(api, "correctPosition").mockResolvedValue({
      from_ordinal: 54,
      to_ordinal: 3,
      removed_units: 51,
      removed_advances: 1,
      moved: true,
      track: track({ ...GEMARA, actual_ordinal: 3 }),
    });
    mountTrack();

    await userEvent.click(await screen.findByRole("button", { name: /amud 3:/ }));
    expect(api.advance).not.toHaveBeenCalled();
    expect(await screen.findByText(/51 amudim behind where you are/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Correct position" }));
    expect(api.correctPosition).toHaveBeenCalledWith("t-gemara", { toOrdinal: 3 }, true);
    expect(await screen.findByText(/51 removed/)).toBeInTheDocument();
  });

  it("falls back to the label when the corrected track has no position", async () => {
    // Corrected back past everything: there is no `at` left to read out in the toast.
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "correctPosition").mockResolvedValue({
      from_ordinal: 54,
      to_ordinal: 3,
      removed_units: 51,
      removed_advances: 1,
      moved: true,
      track: track({ ...GEMARA, actual_ordinal: 0, at: null }),
    });
    mountTrack();

    await userEvent.click(await screen.findByRole("button", { name: /amud 3:/ }));
    await userEvent.click(screen.getByRole("button", { name: "Correct position" }));

    expect(await screen.findByText(/Back to unit 3 — 51 removed/)).toBeInTheDocument();
  });

  it("surfaces a refused correction", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "correctPosition").mockRejectedValue(new ApiError("there is no undo", 422));
    mountTrack();

    await userEvent.click(await screen.findByRole("button", { name: /amud 3:/ }));
    await userEvent.click(screen.getByRole("button", { name: "Correct position" }));

    expect(await screen.findByText("there is no undo")).toBeInTheDocument();
  });

  it("keeps a correction cancellable", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "correctPosition");
    mountTrack();

    await userEvent.click(await screen.findByRole("button", { name: /amud 3:/ }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(api.correctPosition).not.toHaveBeenCalled();
    expect(screen.queryByText(/behind where you are/)).not.toBeInTheDocument();
  });

  it("renders a missing calendar as a waiting banner", async () => {
    vi.spyOn(api, "track").mockRejectedValue(
      new ApiError("no calendar snapshot for 2026-08-25; run the calendar command", 409),
    );
    mountTrack();
    expect(await screen.findByText("The data is not ready yet")).toBeInTheDocument();
  });

  it("renders any other failure as a failure", async () => {
    vi.spyOn(api, "track").mockRejectedValue(new ApiError("boom", 500));
    mountTrack();
    expect(await screen.findByText("That did not work")).toBeInTheDocument();
  });

  it("shows a loading state until the track arrives", () => {
    vi.spyOn(api, "track").mockReturnValue(new Promise(() => undefined));
    mountTrack();
    expect(screen.getByText("Loading the rail…")).toBeInTheDocument();
  });
});

// --- Roadmap ---------------------------------------------------------------------------------

const ROADMAP = [
  {
    track_id: "t-gemara",
    name_en: "Gemara",
    name_he: "גמרא",
    total: 150,
    work_ref_title: null,
    corpus_en: null,
    corpus_total: null,
    corpus_years: null,
    actual_ordinal: 54,
    units_remaining: 96,
    rate_per_day: 1,
    debt: 20,
    projected_finish: "2026-11-28",
    yearly_cycle_rate: 0.41,
  },
  {
    track_id: "t-hadar",
    name_en: "David Hadar",
    name_he: "דוד הדר",
    total: 126,
    work_ref_title: null,
    corpus_en: null,
    corpus_total: null,
    corpus_years: null,
    actual_ordinal: 23,
    units_remaining: 103,
    rate_per_day: 0,
    debt: 0,
    projected_finish: null,
    yearly_cycle_rate: 0.35,
  },
];

describe("RoadmapScreen", () => {
  it("dates every track that has a rate", async () => {
    vi.spyOn(api, "roadmap").mockResolvedValue(ROADMAP);
    mount(<RoadmapScreen />);
    expect(await screen.findByText("2026-11-28")).toBeInTheDocument();
    expect(screen.getByText("no schedule")).toBeInTheDocument();
  });

  it("shows the yearly-cycle rate the Pace Explorer is built on", async () => {
    vi.spyOn(api, "roadmap").mockResolvedValue(ROADMAP);
    mount(<RoadmapScreen />);
    expect(await screen.findByText("0.41/day")).toBeInTheDocument();
  });

  it("shows a dash rather than a zero debt", async () => {
    vi.spyOn(api, "roadmap").mockResolvedValue(ROADMAP);
    mount(<RoadmapScreen />);
    await screen.findByText("2026-11-28");
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("sorts by remaining when asked", async () => {
    vi.spyOn(api, "roadmap").mockResolvedValue(ROADMAP);
    mount(<RoadmapScreen />);
    await screen.findByText("2026-11-28");
    await userEvent.click(screen.getByRole("button", { name: "Remaining" }));
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0] as HTMLElement).getByText("David Hadar")).toBeInTheDocument();
  });

  it("puts a track with no projection last when sorting by date", async () => {
    vi.spyOn(api, "roadmap").mockResolvedValue([ROADMAP[1]!, ROADMAP[0]!]);
    mount(<RoadmapScreen />);
    await screen.findByText("2026-11-28");
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0] as HTMLElement).getByText("Gemara")).toBeInTheDocument();
  });

  it("surfaces a failure", async () => {
    vi.spyOn(api, "roadmap").mockRejectedValue(new ApiError("boom", 500));
    mount(<RoadmapScreen />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});

// --- Chavrusas -------------------------------------------------------------------------------

describe("ChavrusasScreen", () => {
  const person = {
    id: "c1",
    name: "David Hadar",
    notes: "Thursday nights.",
    days_stale: 22,
    tracks: [HADAR],
    sessions: [
      {
        occurred_on: "2026-08-03",
        hebrew_date: "כ׳ באב",
        from_ordinal: 22,
        to_ordinal: 23,
        unit_count: 1,
        note: "finished the sugya",
      },
    ],
  };

  it("shows staleness in the words a person would use", async () => {
    vi.spyOn(api, "chavrusas").mockResolvedValue([person]);
    mount(<ChavrusasScreen />);
    expect(await screen.findByText("3 weeks ago")).toBeInTheDocument();
  });

  it("shows the session log with its notes and Hebrew dates", async () => {
    vi.spyOn(api, "chavrusas").mockResolvedValue([person]);
    mount(<ChavrusasScreen />);
    expect(await screen.findByText("finished the sugya")).toBeInTheDocument();
    expect(screen.getByText("כ׳ באב")).toBeInTheDocument();
    expect(screen.getByText("2026-08-03")).toBeInTheDocument();
  });

  it("says plainly when there are no sessions", async () => {
    vi.spyOn(api, "chavrusas").mockResolvedValue([{ ...person, sessions: [], days_stale: null, notes: null }]);
    mount(<ChavrusasScreen />);
    expect(await screen.findByText("No sessions recorded yet.")).toBeInTheDocument();
    expect(screen.getByText("never learned together")).toBeInTheDocument();
  });

  it("surfaces a failure", async () => {
    vi.spyOn(api, "chavrusas").mockRejectedValue(new ApiError("boom", 500));
    mount(<ChavrusasScreen />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});

// --- Tags ------------------------------------------------------------------------------------

const PARSHA = { id: "g1", name: "parsha", name_he: "פרשה", color: null, track_count: 4 };

describe("TagsScreen", () => {
  it("lists tags with how many tracks wear them", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([PARSHA]);
    mount(<TagsScreen />);
    expect(await screen.findByText("4 tracks")).toBeInTheDocument();
    expect(screen.getByText("פרשה")).toBeInTheDocument();
  });

  it("uses the singular for one track", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([{ ...PARSHA, track_count: 1 }]);
    mount(<TagsScreen />);
    expect(await screen.findByText("1 track")).toBeInTheDocument();
  });

  it("creates a tag", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([]);
    vi.spyOn(api, "createTag").mockResolvedValue(PARSHA);
    mount(<TagsScreen />);
    await userEvent.type(screen.getByLabelText("Name"), "parsha");
    await userEvent.type(screen.getByLabelText("Hebrew (optional)"), "פרשה");
    await userEvent.click(screen.getByRole("button", { name: "Add tag" }));
    expect(api.createTag).toHaveBeenCalledWith({ name: "parsha", name_he: "פרשה", color: null });
  });

  it("sends no Hebrew when the field is left empty", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([]);
    vi.spyOn(api, "createTag").mockResolvedValue(PARSHA);
    mount(<TagsScreen />);
    await userEvent.type(screen.getByLabelText("Name"), "mussar");
    await userEvent.click(screen.getByRole("button", { name: "Add tag" }));
    expect(api.createTag).toHaveBeenCalledWith({ name: "mussar", name_he: null, color: null });
  });

  it("shows a duplicate name as a field error", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([PARSHA]);
    vi.spyOn(api, "createTag").mockRejectedValue(new ApiError("a tag named 'parsha' already exists", 409));
    mount(<TagsScreen />);
    await userEvent.type(screen.getByLabelText("Name"), "parsha");
    await userEvent.click(screen.getByRole("button", { name: "Add tag" }));
    expect(await screen.findByText(/already exists/)).toBeInTheDocument();
  });

  it("renames a tag", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([PARSHA]);
    vi.spyOn(api, "updateTag").mockResolvedValue({ ...PARSHA, name: "parashah" });
    vi.spyOn(window, "prompt").mockReturnValue("parashah");
    mount(<TagsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Rename" }));
    expect(api.updateTag).toHaveBeenCalledWith("g1", { name: "parashah" });
  });

  it("does nothing when a rename is cancelled or unchanged", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([PARSHA]);
    const update = vi.spyOn(api, "updateTag");
    const prompt = vi.spyOn(window, "prompt").mockReturnValue(null);
    mount(<TagsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Rename" }));
    prompt.mockReturnValue("parsha");
    await userEvent.click(screen.getByRole("button", { name: "Rename" }));
    prompt.mockReturnValue("   ");
    await userEvent.click(screen.getByRole("button", { name: "Rename" }));
    expect(update).not.toHaveBeenCalled();
  });

  it("surfaces a failed rename", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([PARSHA]);
    vi.spyOn(api, "updateTag").mockRejectedValue(new ApiError("that name is taken", 409));
    vi.spyOn(window, "prompt").mockReturnValue("mussar");
    mount(<TagsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Rename" }));
    expect(await screen.findByText("that name is taken")).toBeInTheDocument();
  });

  it("warns that a delete removes the label and never the track", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([PARSHA]);
    vi.spyOn(api, "deleteTag").mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    mount(<TagsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(confirm.mock.calls[0]?.[0]).toMatch(/tracks themselves are untouched/);
    expect(api.deleteTag).toHaveBeenCalledWith("g1");
    expect(await screen.findByText(/Deleted the tag/)).toBeInTheDocument();
  });

  it("asks a shorter question for a tag nothing wears", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([{ ...PARSHA, track_count: 0 }]);
    vi.spyOn(api, "deleteTag").mockResolvedValue(undefined);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    mount(<TagsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(confirm.mock.calls[0]?.[0]).toBe('Delete the tag "parsha"?');
  });

  it("does nothing when a delete is declined", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([PARSHA]);
    const remove = vi.spyOn(api, "deleteTag");
    vi.spyOn(window, "confirm").mockReturnValue(false);
    mount(<TagsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(remove).not.toHaveBeenCalled();
  });

  it("surfaces a failed delete", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([PARSHA]);
    vi.spyOn(api, "deleteTag").mockRejectedValue(new ApiError("no tag with that id", 404));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mount(<TagsScreen />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(await screen.findByText("no tag with that id")).toBeInTheDocument();
  });

  it("surfaces a failed load", async () => {
    vi.spyOn(api, "tags").mockRejectedValue(new ApiError("boom", 500));
    mount(<TagsScreen />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});

// --- Alignment -------------------------------------------------------------------------------

describe("AlignmentScreen", () => {
  const rows = [
    { masechta: "Berakhot", links: 71, share: 0.71, is_inferred: false },
    { masechta: "Yoma", links: 8, share: 0.08, is_inferred: true },
  ];

  /** Ein Mishpat maps the codes to their sources, so only a halachic track can be asked. */
  const RAMBAM = track({
    id: "t-cohen",
    name_en: "David Cohen — Mishneh Torah",
    name_he: "דוד כהן",
    at: {
      ref: "Mishneh Torah, Human Dispositions 5:8",
      label_en: "5:8",
      label_he: "ה׳:ח׳",
      work_ref_title: "Mishneh Torah, Human Dispositions",
      work_title_he: "he-deos",
      corpus_ordinal: 136,
      seq_in_work: 48,
      sefaria_url: null,
    },
  });

  it("offers only the tracks the apparatus can answer for", async () => {
    // Seventeen of twenty had no Ein Mishpat to read, and each answered with a blank screen.
    // A track never opened has no position, so there is no work to look up either.
    const unopened = track({ id: "t-new", name_en: "Shulchan Aruch", at: null });
    vi.spyOn(api, "tracks").mockResolvedValue([track(), unopened, RAMBAM]);
    vi.spyOn(api, "alignment").mockResolvedValue(rows);
    mount(<AlignmentScreen />);
    expect(await screen.findByRole("option", { name: /Mishneh Torah/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Neviim" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Shulchan Aruch" })).not.toBeInTheDocument();
  });

  it("asks for the first one it can, rather than opening empty", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([track(), RAMBAM]);
    const alignment = vi.spyOn(api, "alignment").mockResolvedValue(rows);
    mount(<AlignmentScreen />);
    await screen.findByText("71%");
    expect(alignment).toHaveBeenCalledWith("t-cohen");
  });

  it("switches when another halachic track is chosen", async () => {
    const jacob = track({
      ...RAMBAM,
      id: "t-jacob",
      name_en: "Rabbi Jacob — Mishneh Torah",
    });
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM, jacob]);
    const alignment = vi.spyOn(api, "alignment").mockResolvedValue(rows);
    mount(<AlignmentScreen />);
    await screen.findByText("71%");
    await userEvent.selectOptions(screen.getByRole("combobox"), "t-jacob");
    expect(alignment).toHaveBeenLastCalledWith("t-jacob");
  });

  it("says where to start when no track can be asked at all", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([track()]);
    mount(<AlignmentScreen />);
    expect(await screen.findByText(/Nothing to align yet/)).toBeInTheDocument();
  });

  it("shows the ranking as a distribution", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "alignment").mockResolvedValue(rows);
    mount(<AlignmentScreen />);
    expect(await screen.findByText("71%")).toBeInTheDocument();
    expect(screen.getByText("8%")).toBeInTheDocument();
  });

  it("marks an inferred row and explains what that means", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "alignment").mockResolvedValue(rows);
    mount(<AlignmentScreen />);
    await screen.findByText("71%");
    expect(screen.getAllByText("inferred").length).toBeGreaterThan(1);
    expect(document.querySelector(".align__legend")?.textContent).toMatch(/bridged through Tur/);
  });

  it("says plainly when the apparatus reaches nothing", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "alignment").mockResolvedValue([]);
    mount(<AlignmentScreen />);
    expect(await screen.findByText(/honest empty/)).toBeInTheDocument();
  });

  it("surfaces a failure", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "alignment").mockRejectedValue(new ApiError("boom", 500));
    mount(<AlignmentScreen />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("boom");
    });
  });
});
