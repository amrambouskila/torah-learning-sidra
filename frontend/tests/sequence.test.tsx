import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { SequenceScreen } from "@/screens/SequenceScreen";
import { createStore } from "@/stores/store";
import type { SequenceResponse, SequenceStage } from "@/types/SequenceResponse";
import type { TrackRow } from "@/types/TrackRow";

import { GEMARA, track } from "./fixtures";

function stage(overrides: Partial<SequenceStage> = {}): SequenceStage {
  return {
    masechta_en: "Avodah Zarah",
    masechta_he: "עבודה זרה",
    share: 0.42,
    links: 200,
    runner_up: "Sanhedrin",
    works: [
      { ref_title: "Mishneh Torah, Foreign Worship", title_he: "he-fw", halachos: 60 },
      { ref_title: "Mishneh Torah, Repentance", title_he: "he-tsh", halachos: 41 },
    ],
    halachos_in_stage: 101,
    halachos_until: 0,
    is_current: true,
    seen_before: false,
    ...overrides,
  };
}

const BERAKHOT = stage({
  masechta_en: "Berakhot",
  masechta_he: "ברכות",
  share: 0.71,
  links: 106,
  runner_up: "Shabbat",
  works: [{ ref_title: "Mishneh Torah, Reading the Shema", title_he: "he-ks", halachos: 26 }],
  halachos_in_stage: 26,
  halachos_until: 172,
  is_current: false,
});

/** A Rambam chavrusa: the only kind of track this screen can follow. */
const RAMBAM: TrackRow = track({
  id: "t-jacob",
  name_en: "Rabbi Jacob — Mishneh Torah",
  name_he: "הרב יעקב",
  at: {
    ref: "Mishneh Torah, Foreign Worship 5:7",
    label_en: "5:7",
    label_he: "ה׳:ז׳",
    work_ref_title: "Mishneh Torah, Foreign Worship",
    work_title_he: "he-fw",
    corpus_ordinal: 288,
    seq_in_work: 47,
    sefaria_url: null,
  },
});

const GEMARA_ON_AZ: TrackRow = track({
  ...GEMARA,
  total: 150,
  actual_ordinal: 54,
  unit_singular: "amud",
  unit_plural: "amudim",
  at: {
    ref: "Avodah Zarah 28b",
    label_en: "28b",
    label_he: "כ״ח ע״ב",
    work_ref_title: "Avodah Zarah",
    work_title_he: "עבודה זרה",
    corpus_ordinal: 54,
    seq_in_work: 54,
    sefaria_url: null,
  },
});

function body(overrides: Partial<SequenceResponse> = {}): SequenceResponse {
  return {
    track_id: "t-jacob",
    name_en: "Rabbi Jacob — Mishneh Torah",
    name_he: "הרב יעקב",
    at: RAMBAM.at,
    stages: [stage(), BERAKHOT],
    ...overrides,
  };
}

function mount() {
  render(
    <Provider store={createStore()}>
      <MemoryRouter>
        <SequenceScreen />
      </MemoryRouter>
    </Provider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SequenceScreen", () => {
  it("shows a section with no masechta riding along with the one before it", async () => {
    // Amram's rule: Teshuvah has no masechta, so it does not move him off Avodah Zarah.
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "sequence").mockResolvedValue(body());
    mount();
    const current = (await screen.findByText("Avodah Zarah")).closest("li") as HTMLElement;
    expect(current.textContent).toContain("Foreign Worship · Repentance");
    expect(within(current).getByText("learning now")).toBeInTheDocument();
  });

  it("says how far off the next masechta is", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "sequence").mockResolvedValue(body());
    mount();
    const next = (await screen.findByText("Berakhot")).closest("li") as HTMLElement;
    expect(next.textContent).toContain("172");
  });

  it("carries the evidence behind each pairing", async () => {
    // A close call must stay visible rather than being presented as a fact.
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "sequence").mockResolvedValue(body());
    mount();
    const current = (await screen.findByText("Avodah Zarah")).closest("li") as HTMLElement;
    expect(current.textContent).toContain("42");
    expect(current.textContent).toContain("next closest Sanhedrin");
  });

  it("measures the runway against the masechta actually being learned", async () => {
    // The runway is what is left of this stage, not its whole length: he is already partway in.
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM, GEMARA_ON_AZ]);
    vi.spyOn(api, "sequence").mockResolvedValue(body());
    mount();
    const pace = (await screen.findByText(/halachos of runway/)).textContent;
    expect(pace).toContain("96");
    expect(pace).toContain("172");
    expect(pace).toContain("1.8");
  });

  it("says nothing about pace once that masechta is finished", async () => {
    const done = track({ ...GEMARA_ON_AZ, actual_ordinal: 150 });
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM, done]);
    vi.spyOn(api, "sequence").mockResolvedValue(body());
    mount();
    await screen.findByText("Avodah Zarah");
    expect(screen.queryByText(/of runway/)).not.toBeInTheDocument();
  });

  it("says nothing about pace when the code is already at the switch", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM, GEMARA_ON_AZ]);
    vi.spyOn(api, "sequence").mockResolvedValue(
      body({ stages: [stage(), { ...BERAKHOT, halachos_until: 0 }] }),
    );
    mount();
    await screen.findByText("Avodah Zarah");
    expect(screen.queryByText(/of runway/)).not.toBeInTheDocument();
  });

  it("says nothing about pace when no track is on that masechta", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "sequence").mockResolvedValue(body());
    mount();
    await screen.findByText("Avodah Zarah");
    expect(screen.queryByText(/of runway/)).not.toBeInTheDocument();
  });

  it("marks a masechta the code returns to", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "sequence").mockResolvedValue(
      body({ stages: [stage(), { ...BERAKHOT, seen_before: true }] }),
    );
    mount();
    expect(await screen.findByText("already been here")).toBeInTheDocument();
  });

  it("names a run that finds no masechta at all", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "sequence").mockResolvedValue(
      body({
        stages: [stage({ masechta_en: null, masechta_he: null, share: null, links: null, runner_up: null })],
      }),
    );
    mount();
    expect(await screen.findByText("no masechta of its own")).toBeInTheDocument();
  });

  it("offers only the code tracks", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM, GEMARA_ON_AZ, track({ at: null })]);
    vi.spyOn(api, "sequence").mockResolvedValue(body());
    mount();
    expect(await screen.findByRole("option", { name: /Rabbi Jacob/ })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Gemara" })).not.toBeInTheDocument();
  });

  it("switches when another code is chosen", async () => {
    const cohen = track({ ...RAMBAM, id: "t-cohen", name_en: "David Cohen — Mishneh Torah" });
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM, cohen]);
    const spy = vi.spyOn(api, "sequence").mockResolvedValue(body());
    mount();
    await screen.findByText("Avodah Zarah");
    await userEvent.selectOptions(screen.getByRole("combobox"), "t-cohen");
    expect(spy).toHaveBeenLastCalledWith("t-cohen");
  });

  it("says where to start when there is no code track", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([GEMARA_ON_AZ]);
    mount();
    expect(await screen.findByText(/Nothing to sequence yet/)).toBeInTheDocument();
  });

  it("says so when the code is finished", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "sequence").mockResolvedValue(body({ stages: [], at: null }));
    mount();
    expect(await screen.findByText(/this code is finished/)).toBeInTheDocument();
  });

  it("keeps the backend's sentence on failure", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([RAMBAM]);
    vi.spyOn(api, "sequence").mockRejectedValue(new ApiError("not a code track", 422));
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("not a code track");
  });
});
