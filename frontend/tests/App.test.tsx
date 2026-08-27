import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/api/endpoints";
import { App } from "@/App";

import { today } from "./fixtures";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("opens on Today with the sidebar alongside", async () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    render(<App />);
    // Wait for the loaded screen first: the heading is re-created when the loading branch is
    // replaced, so a node grabbed mid-load is detached by the time it is asserted on.
    await screen.findByText("י״ב בֶּאֱלוּל תשפ״ו");
    expect(screen.getByRole("navigation", { name: "Sections" })).toBeInTheDocument();
    expect(screen.getByText("Today", { selector: "h1" })).toBeInTheDocument();
  });

  it("offers every section in the nav", () => {
    vi.spyOn(api, "today").mockResolvedValue(today());
    render(<App />);
    for (const label of ["Today", "Roadmap", "Chavrusas", "Alignment", "Tags"]) {
      expect(screen.getByRole("link", { name: new RegExp(label) })).toBeInTheDocument();
    }
  });
});
