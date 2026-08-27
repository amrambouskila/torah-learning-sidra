import type { PositionModel } from "@/types/PositionModel";
import type { TodayResponse } from "@/types/TodayResponse";
import type { TrackRow } from "@/types/TrackRow";

export function position(ref: string, hebrew: string, ordinal: number): PositionModel {
  return {
    ref,
    label_en: ref,
    label_he: hebrew,
    work_ref_title: ref.split(" ")[0] ?? ref,
    work_title_he: hebrew,
    corpus_ordinal: ordinal,
    seq_in_work: ordinal,
    sefaria_url: `https://www.sefaria.org/${ref.replace(/ /g, "_")}`,
  };
}

export function track(overrides: Partial<TrackRow> = {}): TrackRow {
  return {
    id: "t-neviim",
    name_en: "Neviim",
    name_he: "נביאים",
    category: "daily",
    kind: "corpus",
    period: "day",
    rate: 1,
    total: 380,
    cycle_length: null,
    cycle_index: null,
    reachable_to: 380,
    actual_ordinal: 120,
    unit_singular: "perek",
    unit_plural: "perakim",
    at: position("Jeremiah 44", "מ״ד", 120),
    up_next: position("Jeremiah 45", "מ״ה", 121),
    scheduled_at: position("Jeremiah 47", "מ״ז", 123),
    debt: 3,
    days_ahead: 0,
    is_behind: true,
    starts_in_days: null,
    starts_on: null,
    is_finished: false,
    last_advanced_on: "2026-08-24",
    days_stale: 1,
    tags: [],
    chavrusa: null,
    ...overrides,
  };
}

/** Amram's real opening: Avoda Zara twenty amudim behind, Yirmiyahu three perakim behind. */
export const GEMARA = track({
  id: "t-gemara",
  name_en: "Gemara",
  name_he: "גמרא",
  kind: "curated_queue",
  total: 150,
  reachable_to: 150,
  actual_ordinal: 54,
  unit_singular: "amud",
  unit_plural: "amudim",
  at: position("Avodah Zarah 28b", "כ״ח ע״ב", 54),
  up_next: position("Avodah Zarah 29a", "כ״ט ע״א", 55),
  scheduled_at: position("Avodah Zarah 38b", "ל״ח ע״ב", 74),
  debt: 20,
});

export const CHUMASH = track({
  id: "t-chumash",
  name_en: "Chumash",
  name_he: "חומש",
  kind: "parsha_aliyah",
  total: 378,
  reachable_to: 378,
  actual_ordinal: 346,
  unit_singular: "aliyah",
  unit_plural: "aliyot",
  debt: 0,
  is_behind: false,
  tags: ["parsha"],
});

export const LIKUTEI = track({
  id: "t-likutei",
  name_en: "Likutei Sichot",
  name_he: "ליקוטי שיחות",
  category: "shabbat",
  kind: "parsha_weekly",
  period: "week",
  total: 54,
  reachable_to: 54,
  actual_ordinal: 0,
  unit_singular: "parsha",
  unit_plural: "parshiyos",
  at: null,
  up_next: { ...position("Likutei Sichot 1", "בראשית", 1), sefaria_url: null },
  scheduled_at: null,
  debt: 0,
  is_behind: false,
  starts_in_days: 47,
  starts_on: "2026-10-11",
  last_advanced_on: null,
  days_stale: null,
  tags: ["parsha"],
});

export const HADAR = track({
  id: "t-hadar",
  name_en: "David Hadar — Brachot",
  name_he: "דוד הדר",
  category: "chavrusa",
  kind: "curated_queue",
  period: "none",
  total: 126,
  reachable_to: 126,
  actual_ordinal: 23,
  unit_singular: "amud",
  unit_plural: "amudim",
  at: position("Berakhot 13a", "י״ג ע״א", 23),
  up_next: position("Berakhot 13b", "י״ג ע״ב", 24),
  scheduled_at: null,
  debt: null,
  is_behind: false,
  days_stale: 22,
  chavrusa: "David Hadar",
});

export function today(overrides: Partial<TodayResponse> = {}): TodayResponse {
  return {
    civil_date: "2026-08-25",
    hebrew_date: "י״ב בֶּאֱלוּל תשפ״ו",
    parsha_en: ["Ki Tavo"],
    parsha_he: ["כי תבוא"],
    is_yom_tov: false,
    daily: [CHUMASH, track(), GEMARA],
    shabbat: [LIKUTEI],
    chavrusa: [HADAR],
    ...overrides,
  };
}
