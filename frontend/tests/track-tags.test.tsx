import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { ToastStack } from "@/components/ToastStack";
import { TrackScreen } from "@/screens/TrackScreen";
import { createStore } from "@/stores/store";
import type { TagRead } from "@/types/TagRead";

import { GEMARA, track } from "./fixtures";

const ORAL: TagRead = { id: "tag-oral", name: "oral torah", name_he: null, color: null, track_count: 0 };
const WRITTEN: TagRead = { id: "tag-written", name: "written torah", name_he: null, color: null, track_count: 0 };

function mount() {
  render(
    <Provider store={createStore()}>
      <MemoryRouter initialEntries={["/tracks/t-gemara"]}>
        <Routes>
          <Route path="/tracks/:trackId" element={<TrackScreen />} />
        </Routes>
        <ToastStack />
      </MemoryRouter>
    </Provider>,
  );
}

function stub(tags: readonly TagRead[], on: readonly string[] = []) {
  vi.spyOn(api, "track").mockResolvedValue({
    track: track({ ...GEMARA, tags: [...on] }),
    rail: [],
    rail_from: 0,
    rail_to: 0,
  });
  vi.spyOn(api, "rail").mockResolvedValue([]);
  vi.spyOn(api, "tags").mockResolvedValue(tags);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("tagging a track", () => {
  it("offers every tag there is, lit when this track wears it", async () => {
    stub([ORAL, WRITTEN], ["written torah"]);
    mount();
    expect(await screen.findByRole("button", { name: "oral torah" })).toHaveAttribute(
      "data-active",
      "false",
    );
    expect(screen.getByRole("button", { name: "written torah" })).toHaveAttribute("data-active", "true");
  });

  it("sends the whole set rather than a change to it", async () => {
    // Two quick toggles must not interleave into a state neither of them meant.
    stub([ORAL, WRITTEN], ["written torah"]);
    const spy = vi
      .spyOn(api, "setTrackTags")
      .mockResolvedValue(track({ ...GEMARA, tags: ["oral torah", "written torah"] }));
    mount();
    await userEvent.click(await screen.findByRole("button", { name: "oral torah" }));
    expect(spy).toHaveBeenCalledWith("t-gemara", ["tag-oral", "tag-written"]);
  });

  it("takes a tag off again", async () => {
    stub([ORAL, WRITTEN], ["oral torah"]);
    const spy = vi.spyOn(api, "setTrackTags").mockResolvedValue(track({ ...GEMARA, tags: [] }));
    mount();
    await userEvent.click(await screen.findByRole("button", { name: "oral torah" }));
    expect(spy).toHaveBeenCalledWith("t-gemara", []);
  });

  it("lights the pill from the row the server sends back", async () => {
    stub([ORAL], []);
    vi.spyOn(api, "setTrackTags").mockResolvedValue(track({ ...GEMARA, tags: ["oral torah"] }));
    mount();
    const pill = await screen.findByRole("button", { name: "oral torah" });
    await userEvent.click(pill);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "oral torah" })).toHaveAttribute("data-active", "true");
    });
  });

  it("says where to make one when there are none", async () => {
    stub([]);
    mount();
    expect(await screen.findByText(/No tags yet/)).toBeInTheDocument();
  });

  it("keeps the backend's sentence when the change is refused", async () => {
    stub([ORAL]);
    vi.spyOn(api, "setTrackTags").mockRejectedValue(new ApiError("no tag with id tag-oral", 404));
    mount();
    await userEvent.click(await screen.findByRole("button", { name: "oral torah" }));
    expect(await screen.findByText("no tag with id tag-oral")).toBeInTheDocument();
  });
});
