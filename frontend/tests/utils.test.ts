import { describe, expect, it } from "vitest";

import { byDebt } from "@/utils/byDebt";
import { correctionPhrase } from "@/utils/correctionPhrase";
import { dayWorth } from "@/utils/dayWorth";
import { debtPhrase } from "@/utils/debtPhrase";
import { failureMessage } from "@/utils/failureMessage";
import { percentDone } from "@/utils/percentDone";
import { stalenessPhrase } from "@/utils/stalenessPhrase";

import { track } from "./fixtures";

describe("debtPhrase", () => {
  it("names the units when behind", () => {
    // The spec's opening line reads "20 amudim behind", not "20 behind".
    const phrase = debtPhrase(track({ debt: 20, unit_singular: "amud", unit_plural: "amudim" }));
    expect(phrase).toEqual({ tone: "behind", value: "20", suffix: "amudim behind" });
  });

  it("uses the singular for one unit", () => {
    expect(debtPhrase(track({ debt: 1 })).suffix).toBe("perek behind");
  });

  it("shows a surplus as days ahead, never as a negative", () => {
    const phrase = debtPhrase(track({ debt: -3, days_ahead: 3, is_behind: false }));
    expect(phrase).toEqual({ tone: "ahead", value: "3", suffix: "days ahead" });
    expect(phrase.value).not.toContain("-");
  });

  it("uses the singular for one day ahead", () => {
    expect(debtPhrase(track({ debt: -1, days_ahead: 1, is_behind: false })).suffix).toBe("day ahead");
  });

  it("says on pace when square", () => {
    expect(debtPhrase(track({ debt: 0, days_ahead: 0, is_behind: false }))).toEqual({
      tone: "level",
      value: "",
      suffix: "on pace",
    });
  });

  it("counts down a track that has not started", () => {
    expect(debtPhrase(track({ starts_in_days: 47 }))).toEqual({
      tone: "waiting",
      value: "7",
      suffix: "weeks away",
    });
  });

  it("counts a near start date in days rather than rounding it up to a week", () => {
    // Deliberate change: this used to read "week away" for five days out, which was invisible
    // while every start date was seven weeks away and wrong once a date can be picked.
    expect(debtPhrase(track({ starts_in_days: 5 })).suffix).toBe("days away");
    expect(debtPhrase(track({ starts_in_days: 7 })).suffix).toBe("week away");
  });

  it("puts finished ahead of any debt", () => {
    // A finished track is not "behind" however long ago the schedule ran past it.
    expect(debtPhrase(track({ is_finished: true, debt: 99 }))).toEqual({
      tone: "done",
      value: "",
      suffix: "finished",
    });
  });

  it("puts not-yet-started ahead of finished", () => {
    expect(debtPhrase(track({ starts_in_days: 7, is_finished: true })).tone).toBe("waiting");
  });

  it("reports staleness in weeks for a chavrusa track", () => {
    expect(debtPhrase(track({ debt: null, days_stale: 22 }))).toEqual({
      tone: "stale",
      value: "3",
      suffix: "weeks since",
    });
  });

  it("uses the singular for one week since", () => {
    expect(debtPhrase(track({ debt: null, days_stale: 8 })).suffix).toBe("week since");
  });

  it("reports days when it is less than a week", () => {
    expect(debtPhrase(track({ debt: null, days_stale: 3 })).suffix).toBe("days since");
    expect(debtPhrase(track({ debt: null, days_stale: 1 })).suffix).toBe("day since");
  });

  it("says plainly when a chavrusa track has never moved", () => {
    expect(debtPhrase(track({ debt: null, days_stale: null }))).toEqual({
      tone: "stale",
      value: "",
      suffix: "never learned",
    });
  });
});

describe("byDebt", () => {
  it("puts the most behind first", () => {
    const rows = [track({ id: "a", debt: 3 }), track({ id: "b", debt: 20 })].sort(byDebt);
    expect(rows.map((row) => row.id)).toEqual(["b", "a"]);
  });

  it("sorts a not-yet-started track last however large its nominal debt", () => {
    const rows = [
      track({ id: "waiting", starts_in_days: 47, debt: 99 }),
      track({ id: "behind", debt: 1 }),
    ].sort(byDebt);
    expect(rows.map((row) => row.id)).toEqual(["behind", "waiting"]);
  });

  it("orders chavrusa tracks by staleness", () => {
    const rows = [
      track({ id: "fresh", debt: null, days_stale: 2 }),
      track({ id: "stale", debt: null, days_stale: 40 }),
    ].sort(byDebt);
    expect(rows.map((row) => row.id)).toEqual(["stale", "fresh"]);
  });

  it("puts a never-met track above any measured staleness", () => {
    const rows = [
      track({ id: "met", debt: null, days_stale: 400 }),
      track({ id: "never", debt: null, days_stale: null }),
    ].sort(byDebt);
    expect(rows.map((row) => row.id)).toEqual(["never", "met"]);
  });

  it("breaks a tie by name so the order is stable between requests", () => {
    const rows = [
      track({ id: "z", name_en: "Zohar", debt: 0 }),
      track({ id: "a", name_en: "Avot", debt: 0 }),
    ].sort(byDebt);
    expect(rows.map((row) => row.name_en)).toEqual(["Avot", "Zohar"]);
  });
});

describe("percentDone", () => {
  it("rounds to a whole percent", () => {
    expect(percentDone(track({ actual_ordinal: 120, total: 380 }))).toBe(32);
  });

  it("reports zero for a track with nothing in it rather than dividing by zero", () => {
    expect(percentDone(track({ actual_ordinal: 0, total: 0 }))).toBe(0);
  });

  it("reports a hundred at the end", () => {
    expect(percentDone(track({ actual_ordinal: 380, total: 380 }))).toBe(100);
  });
});

describe("stalenessPhrase", () => {
  it.each([
    [null, "never learned together"],
    [0, "today"],
    [1, "yesterday"],
    [5, "5 days ago"],
    [13, "13 days ago"],
    [14, "2 weeks ago"],
    [21, "3 weeks ago"],
    [62, "8 weeks ago"],
    [63, "2 months ago"],
    [30, "4 weeks ago"],
  ])("turns %s days into %s", (days, expected) => {
    expect(stalenessPhrase(days)).toBe(expected);
  });

  it("reaches months only once weeks run out", () => {
    expect(stalenessPhrase(400)).toBe("13 months ago");
  });
});

describe("failureMessage", () => {
  it("takes an Error's message", () => {
    expect(failureMessage(new Error("boom"), "fallback")).toBe("boom");
  });

  it("takes the message off a rejected thunk payload", () => {
    // `unwrap()` throws the reject payload, not an Error — this is where the backend's own
    // sentence would otherwise be silently swapped for a generic one.
    expect(failureMessage({ message: "the track holds 150 units", isConflict: false }, "fallback")).toBe(
      "the track holds 150 units",
    );
  });

  it("falls back on an empty message", () => {
    expect(failureMessage({ message: "" }, "fallback")).toBe("fallback");
  });

  it("falls back on a non-string message", () => {
    expect(failureMessage({ message: 42 }, "fallback")).toBe("fallback");
  });

  it("falls back on anything else", () => {
    expect(failureMessage("a bare string", "fallback")).toBe("fallback");
    expect(failureMessage(null, "fallback")).toBe("fallback");
    expect(failureMessage(undefined, "fallback")).toBe("fallback");
  });
});

describe("correctionPhrase", () => {
  it("uses the singular for one unit and the plural beyond", () => {
    const row = track({ unit_singular: "perek", unit_plural: "perakim" });
    expect(correctionPhrase(row, 263, 262)).toContain("1 perek behind");
    expect(correctionPhrase(row, 263, 260)).toContain("3 perakim behind");
  });

  it("names the cost and says there is no undo", () => {
    const row = track({ unit_singular: "amud", unit_plural: "amudim" });
    const phrase = correctionPhrase(row, 54, 52);
    expect(phrase).toContain("removes 2 amudim of recorded learning");
    expect(phrase).toContain("no undo");
  });
});

describe("dayWorth", () => {
  it("counts a flat-rate day in the track's own units", () => {
    expect(dayWorth(track({ rate: 1 }))).toBe("one day is 1 perek here");
    expect(dayWorth(track({ rate: 3 }))).toBe("one day is 3 perakim here");
  });

  it("counts a weekly track by the week", () => {
    expect(dayWorth(track({ period: "week", rate: 1 }))).toBe("one week is 1 perek here");
  });

  it("says what the calendar hands out on the parsha tracks", () => {
    // Their pace is the calendar's, not a rate, so a combined week doubles the load.
    expect(dayWorth(track({ kind: "parsha_aliyah" }))).toContain("2 in a combined week");
    expect(dayWorth(track({ kind: "parsha_weekly" }))).toContain("one week is 1 unit");
  });
});
