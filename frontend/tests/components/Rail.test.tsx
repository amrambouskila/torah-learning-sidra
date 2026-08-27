import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/api/endpoints";
import { Rail } from "@/components/Rail";
import { chunksFor, ROW_HEIGHT, visibleSpan } from "@/hooks/useRailWindow";
import type { RailUnit } from "@/types/RailUnit";
import { railState } from "@/utils/railState";

/** Avoda Zara: 150 amudim, lit to 28b at ordinal 54, ghost at 38b at ordinal 74. */
const ACTUAL = 54;
const SCHEDULED = 74;

/** Tall enough to hold all 150 amudim at once, so a marker test is about markers, not scrolling. */
const WHOLE_TRACK = 150 * ROW_HEIGHT;

function unit(ordinal: number): RailUnit {
  return {
    ordinal,
    ref: `Avodah Zarah ${String(ordinal)}`,
    work_title_en: "Avodah Zarah",
    work_title_he: "עבודה זרה",
    label_en: `amud ${String(ordinal)}`,
    label_he: `דף ${String(ordinal)}`,
    sefaria_url: `https://www.sefaria.org/Avodah_Zarah_${String(ordinal)}`,
    is_actual: ordinal === ACTUAL,
    is_scheduled: ordinal === SCHEDULED,
  };
}

function stubRail(): void {
  vi.spyOn(api, "rail").mockImplementation((_id, from, to) => {
    const units: RailUnit[] = [];
    for (let ordinal = from; ordinal <= to; ordinal += 1) units.push(unit(ordinal));
    return Promise.resolve(units);
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("railState", () => {
  it.each([
    [1, "done"],
    [53, "done"],
    [54, "actual"],
    [55, "between"],
    [73, "between"],
    [74, "scheduled"],
    [75, "ahead"],
  ] as const)("puts ordinal %i in the %s state", (ordinal, expected) => {
    expect(railState(ordinal, ACTUAL, SCHEDULED)).toBe(expected);
  });

  it("has no between or scheduled state on a track with no schedule", () => {
    // A chavrusa track carries staleness, not debt, so there is no ghost marker to draw.
    expect(railState(60, ACTUAL, null)).toBe("ahead");
    expect(railState(1, ACTUAL, null)).toBe("done");
    expect(railState(ACTUAL, ACTUAL, null)).toBe("actual");
  });
});

describe("visibleSpan", () => {
  it("starts at one however far back the overscan reaches", () => {
    expect(visibleSpan(0, 340, 150).first).toBe(1);
  });

  it("never runs past the end of the track", () => {
    expect(visibleSpan(150 * ROW_HEIGHT, 340, 150).last).toBe(150);
  });

  it("follows the scroll position", () => {
    const span = visibleSpan(50 * ROW_HEIGHT, 340, 5349);
    expect(span.first).toBeLessThanOrEqual(51);
    expect(span.last).toBeGreaterThan(51);
  });
});

describe("chunksFor", () => {
  it("covers one chunk when the span sits inside it", () => {
    expect(chunksFor(1, 40)).toEqual([0]);
  });

  it("covers both when the span straddles a boundary", () => {
    expect(chunksFor(95, 130)).toEqual([0, 1]);
  });

  it("covers every chunk of a long span", () => {
    expect(chunksFor(1, 250)).toEqual([0, 1, 2]);
  });
});

describe("Rail", () => {
  it("lights the spine to the actual marker and ghosts the scheduled one", async () => {
    stubRail();
    render(
      <Rail
        trackId="t1"
        total={150}
        actual={ACTUAL}
        scheduled={SCHEDULED}
        height={WHOLE_TRACK}
        onSelect={vi.fn()}
      />,
    );

    const actual = await screen.findByRole("button", { name: /amud 54: where you are/ });
    expect(actual).toHaveAttribute("data-state", "actual");

    const ghost = await screen.findByRole("button", { name: /amud 74: where the schedule is/ });
    expect(ghost).toHaveAttribute("data-state", "scheduled");
  });

  it("marks the gap between the markers as owed", async () => {
    stubRail();
    render(
      <Rail
        trackId="t1"
        total={150}
        actual={ACTUAL}
        scheduled={SCHEDULED}
        height={WHOLE_TRACK}
        onSelect={vi.fn()}
      />,
    );
    const owed = await screen.findByRole("button", { name: /amud 60: owed/ });
    expect(owed).toHaveAttribute("data-state", "between");
  });

  it("keeps the DOM bounded on a 5,349-unit track", async () => {
    // The whole point of windowing: Shas does not become 5,349 DOM nodes.
    stubRail();
    render(<Rail trackId="t1" total={5349} actual={1} scheduled={20} onSelect={vi.fn()} />);
    await screen.findByRole("button", { name: /amud 1:/ });
    await waitFor(() => {
      expect(screen.getAllByRole("button").length).toBeLessThan(120);
    });
  });

  it("asks the server only for the span it needs", async () => {
    stubRail();
    render(<Rail trackId="t1" total={5349} actual={1} scheduled={20} onSelect={vi.fn()} />);
    await screen.findByRole("button", { name: /amud 1:/ });
    for (const call of vi.mocked(api.rail).mock.calls) {
      expect(call[2] - call[1]).toBeLessThan(500);
    }
  });

  it("hands the chosen ordinal to its caller", async () => {
    stubRail();
    const onSelect = vi.fn();
    render(
      <Rail
        trackId="t1"
        total={150}
        actual={ACTUAL}
        scheduled={SCHEDULED}
        height={WHOLE_TRACK}
        onSelect={onSelect}
      />,
    );
    await userEvent.click(await screen.findByRole("button", { name: /amud 60: owed/ }));
    expect(onSelect).toHaveBeenCalledWith(60);
  });

  it("deep-links each unit to Sefaria", async () => {
    stubRail();
    render(
      <Rail
        trackId="t1"
        total={150}
        actual={ACTUAL}
        scheduled={SCHEDULED}
        height={WHOLE_TRACK}
        onSelect={vi.fn()}
      />,
    );
    const link = await screen.findByRole("link", { name: "Avodah Zarah 54" });
    expect(link).toHaveAttribute("href", "https://www.sefaria.org/Avodah_Zarah_54");
    expect(link).toHaveAttribute("rel", "noreferrer noopener");
  });

  it("renders a unit that is not on Sefaria as plain text", async () => {
    vi.spyOn(api, "rail").mockResolvedValue([{ ...unit(1), sefaria_url: null, ref: "Likutei Sichot 1" }]);
    render(<Rail trackId="t1" total={1} actual={1} scheduled={null} onSelect={vi.fn()} />);
    expect(await screen.findByText("Likutei Sichot 1")).toHaveClass("ref--plain");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows the failure rather than an empty spine", async () => {
    vi.spyOn(api, "rail").mockRejectedValue(new Error("the rail could not be reached"));
    render(<Rail trackId="t1" total={150} actual={1} scheduled={null} onSelect={vi.fn()} />);
    expect(await screen.findByText("the rail could not be reached")).toBeInTheDocument();
  });

  it("reports a non-Error failure in words", async () => {
    vi.spyOn(api, "rail").mockRejectedValue("nope");
    render(<Rail trackId="t1" total={150} actual={1} scheduled={null} onSelect={vi.fn()} />);
    expect(await screen.findByText("The rail could not be loaded.")).toBeInTheDocument();
  });

  it("brings later ordinals in as it scrolls", async () => {
    stubRail();
    render(<Rail trackId="t1" total={5349} actual={1} scheduled={null} onSelect={vi.fn()} />);
    await screen.findByRole("button", { name: /amud 1:/ });
    expect(screen.queryByRole("button", { name: /amud 200:/ })).not.toBeInTheDocument();

    fireEvent.scroll(screen.getByTestId("rail-viewport"), {
      target: { scrollTop: 200 * ROW_HEIGHT },
    });
    expect(await screen.findByRole("button", { name: /amud 200:/ })).toBeInTheDocument();
  });

  it("asks for nothing on an empty track", () => {
    stubRail();
    render(<Rail trackId="t1" total={0} actual={0} scheduled={null} onSelect={vi.fn()} />);
    expect(api.rail).not.toHaveBeenCalled();
  });
});
