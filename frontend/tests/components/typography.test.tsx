import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HebrewText } from "@/components/HebrewText";
import { LatinGloss } from "@/components/LatinGloss";
import { Numeral } from "@/components/Numeral";

const AVODA_ZARA = "עבודה זרה כ״ח ע״ב";

/** Codepoints, not UTF-16 units: the whole point is to compare what actually rendered. */
function codepoints(text: string): number[] {
  const points: number[] = [];
  for (const character of text) points.push(character.codePointAt(0) ?? 0);
  return points;
}

describe("HebrewText", () => {
  it("renders inside an RTL isolate", () => {
    render(<HebrewText>{AVODA_ZARA}</HebrewText>);
    const node = screen.getByText(AVODA_ZARA);
    expect(node).toHaveAttribute("dir", "rtl");
    expect(node).toHaveAttribute("lang", "he");
    expect(node).toHaveClass("he");
  });

  it("carries the text through verbatim, codepoint for codepoint", () => {
    // The defect this guards: a hand-written Cyrillic Che (U+04B4) once stood in for gershayim.
    render(<HebrewText>{AVODA_ZARA}</HebrewText>);
    const rendered = screen.getByText(AVODA_ZARA).textContent;
    expect(codepoints(rendered)).toEqual(codepoints(AVODA_ZARA));
    expect(rendered).not.toMatch(/&#\d+;/);
  });

  it("renders every Hebrew character inside the Hebrew block or a known separator", () => {
    render(<HebrewText>{AVODA_ZARA}</HebrewText>);
    const separators = new Set([" ", ",", ":", ".", "-", "(", ")"]);
    for (const character of screen.getByText(AVODA_ZARA).textContent) {
      const code = character.codePointAt(0) ?? 0;
      const isHebrew = code >= 0x0590 && code <= 0x05ff;
      expect(isHebrew || separators.has(character) || /\d/.test(character)).toBe(true);
    }
  });

  it.each([
    ["span", "row"],
    ["h1", "display"],
    ["h2", "headline"],
    ["h3", "row"],
  ] as const)("renders as %s at %s size", (as, size) => {
    render(
      <HebrewText as={as} size={size}>
        {AVODA_ZARA}
      </HebrewText>,
    );
    expect(screen.getByText(AVODA_ZARA).tagName.toLowerCase()).toBe(as);
  });

  it("takes an extra class without losing its own", () => {
    render(<HebrewText className="row__title">{AVODA_ZARA}</HebrewText>);
    expect(screen.getByText(AVODA_ZARA)).toHaveClass("he", "row__title");
  });
});

describe("LatinGloss", () => {
  it("renders the transliteration left to right", () => {
    render(<LatinGloss>Avoda Zara 28b</LatinGloss>);
    const node = screen.getByText("Avoda Zara 28b");
    expect(node).toHaveAttribute("dir", "ltr");
    expect(node).toHaveClass("gloss");
  });

  it("takes an extra class without losing its own", () => {
    render(<LatinGloss className="row__gloss">Avoda Zara 28b</LatinGloss>);
    expect(screen.getByText("Avoda Zara 28b")).toHaveClass("gloss", "row__gloss");
  });
});

describe("Numeral", () => {
  it("renders countable values in the mono face", () => {
    render(<Numeral>20</Numeral>);
    expect(screen.getByText("20")).toHaveClass("num");
  });

  it("accepts a string as readily as a number", () => {
    render(<Numeral>2026-11-28</Numeral>);
    expect(screen.getByText("2026-11-28")).toHaveClass("num");
  });

  it("takes a title for the long form of a short label", () => {
    render(<Numeral title="20 amudim behind">20</Numeral>);
    expect(screen.getByText("20")).toHaveAttribute("title", "20 amudim behind");
  });

  it("takes an extra class without losing its own", () => {
    render(<Numeral className="debt">20</Numeral>);
    expect(screen.getByText("20")).toHaveClass("num", "debt");
  });
});
