import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { loadAlignment } from "@/stores/alignmentSlice";
import { loadChavrusas } from "@/stores/chavrusasSlice";
import { loadRoadmap } from "@/stores/roadmapSlice";
import { pollJob } from "@/stores/jobSlice";
import { loadMaintenance } from "@/stores/maintenanceSlice";
import { createStore } from "@/stores/store";
import { createTag, deleteTag, loadTags, updateTag } from "@/stores/tagsSlice";
import { dismissToast, pushToast } from "@/stores/toastSlice";
import { loadToday } from "@/stores/todaySlice";
import { advanceTrack, correctPosition, correctSchedule, loadTracks } from "@/stores/tracksSlice";
import type { TagRead } from "@/types/TagRead";
import type { TrackRow } from "@/types/TrackRow";

const TRACK: TrackRow = {
  id: "t1",
  name_en: "Neviim",
  name_he: "נביאים",
  category: "daily",
  kind: "corpus",
  period: "day",
  rate: 1,
  total: 380,
  cycle_length: null,
  cycle_index: null,
  reachable_to: 150,
  actual_ordinal: 120,
  unit_singular: "perek",
  unit_plural: "perakim",
  at: null,
  up_next: null,
  scheduled_at: null,
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
};

const TAG: TagRead = { id: "g1", name: "parsha", name_he: "פרשה", color: null, track_count: 2 };

afterEach(() => {
  vi.restoreAllMocks();
});

describe("a read-only slice", () => {
  it("moves idle to loading to ready", async () => {
    vi.spyOn(api, "roadmap").mockResolvedValue([]);
    const store = createStore();
    expect(store.getState().roadmap.status).toBe("idle");
    const pending = store.dispatch(loadRoadmap(undefined));
    expect(store.getState().roadmap.status).toBe("loading");
    await pending;
    expect(store.getState().roadmap.status).toBe("ready");
  });

  it("keeps the backend's own sentence on failure", async () => {
    vi.spyOn(api, "today").mockRejectedValue(
      new ApiError("no calendar snapshot for 2026-08-25; run the calendar command", 409),
    );
    const store = createStore();
    await store.dispatch(loadToday(undefined));
    const { status, error, isConflict } = store.getState().today;
    expect(status).toBe("failed");
    expect(error).toMatch(/calendar command/);
    expect(isConflict).toBe(true);
  });

  it("marks a non-409 failure as not a conflict", async () => {
    vi.spyOn(api, "chavrusas").mockRejectedValue(new ApiError("boom", 500));
    const store = createStore();
    await store.dispatch(loadChavrusas(undefined));
    expect(store.getState().chavrusas.isConflict).toBe(false);
  });

  it("survives a rejection that is not an Error at all", async () => {
    vi.spyOn(api, "alignment").mockRejectedValue("a bare string");
    const store = createStore();
    await store.dispatch(loadAlignment("t1"));
    expect(store.getState().alignment.error).toBe("The request failed.");
  });

  it("keeps a plain Error message", async () => {
    vi.spyOn(api, "roadmap").mockRejectedValue(new TypeError("Failed to fetch"));
    const store = createStore();
    await store.dispatch(loadRoadmap(undefined));
    expect(store.getState().roadmap.error).toBe("Failed to fetch");
  });

  it("passes a pinned day through to the endpoint", async () => {
    const spy = vi.spyOn(api, "tracks").mockResolvedValue([]);
    const store = createStore();
    await store.dispatch(loadTracks("2026-08-25"));
    expect(spy).toHaveBeenCalledWith({ on: "2026-08-25" });
  });

  it("omits the day when none is pinned", async () => {
    const spy = vi.spyOn(api, "tracks").mockResolvedValue([]);
    const store = createStore();
    await store.dispatch(loadTracks(undefined));
    expect(spy).toHaveBeenCalledWith({});
  });
});

describe("advancing a track", () => {
  beforeEach(() => {
    vi.spyOn(api, "tracks").mockResolvedValue([TRACK]);
  });

  it("replaces the row from the response rather than refetching", async () => {
    const moved: TrackRow = { ...TRACK, actual_ordinal: 123, debt: 0, is_behind: false };
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: "a1",
      from_ordinal: 120,
      to_ordinal: 123,
      resolved_ordinal: 123,
      unit_count: 3,
      was_replay: false,
      track: moved,
    });
    const store = createStore();
    await store.dispatch(loadTracks(undefined));
    await store.dispatch(advanceTrack({ trackId: "t1", destination: { toOrdinal: 123 } }));
    expect(store.getState().tracks.data[0]?.debt).toBe(0);
  });

  it("leaves other rows alone", async () => {
    const other: TrackRow = { ...TRACK, id: "t2", name_en: "Ketuvim" };
    vi.spyOn(api, "tracks").mockResolvedValue([TRACK, other]);
    vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: "a1",
      from_ordinal: 120,
      to_ordinal: 121,
      resolved_ordinal: 121,
      unit_count: 1,
      was_replay: false,
      track: { ...TRACK, actual_ordinal: 121 },
    });
    const store = createStore();
    await store.dispatch(loadTracks(undefined));
    await store.dispatch(advanceTrack({ trackId: "t1", destination: { toOrdinal: 121 } }));
    expect(store.getState().tracks.data[1]?.name_en).toBe("Ketuvim");
  });

  it("sends a note when one is given and omits it otherwise", async () => {
    const spy = vi.spyOn(api, "advance").mockResolvedValue({
      advance_id: "a1",
      from_ordinal: 120,
      to_ordinal: 121,
      resolved_ordinal: 121,
      unit_count: 1,
      was_replay: false,
      track: TRACK,
    });
    const store = createStore();
    await store.dispatch(advanceTrack({ trackId: "t1", destination: { toRef: "45" }, note: "on the train" }));
    expect(spy).toHaveBeenCalledWith("t1", { toRef: "45" }, { note: "on the train" });
    await store.dispatch(advanceTrack({ trackId: "t1", destination: { toOrdinal: 122 } }));
    expect(spy).toHaveBeenCalledWith("t1", { toOrdinal: 122 }, {});
  });

  it("reports a refused advance without moving the row", async () => {
    vi.spyOn(api, "advance").mockRejectedValue(new ApiError("the track holds 380 units", 422));
    const store = createStore();
    await store.dispatch(loadTracks(undefined));
    const result = await store.dispatch(advanceTrack({ trackId: "t1", destination: { toOrdinal: 9999 } }));
    expect(result.type).toBe("tracks/advance/rejected");
    expect(store.getState().tracks.data[0]?.actual_ordinal).toBe(120);
  });
});

describe("tags", () => {
  it("keeps the list sorted after a create", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([TAG]);
    vi.spyOn(api, "createTag").mockResolvedValue({ ...TAG, id: "g2", name: "mussar" });
    const store = createStore();
    await store.dispatch(loadTags(undefined));
    await store.dispatch(createTag({ name: "mussar", name_he: null, color: null }));
    expect(store.getState().tags.data.map((tag) => tag.name)).toEqual(["mussar", "parsha"]);
  });

  it("replaces the renamed tag and re-sorts", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([TAG, { ...TAG, id: "g2", name: "zohar" }]);
    vi.spyOn(api, "updateTag").mockResolvedValue({ ...TAG, name: "aparsha" });
    const store = createStore();
    await store.dispatch(loadTags(undefined));
    await store.dispatch(updateTag({ id: "g1", changes: { name: "aparsha" } }));
    expect(store.getState().tags.data.map((tag) => tag.name)).toEqual(["aparsha", "zohar"]);
  });

  it("drops the deleted tag", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([TAG]);
    vi.spyOn(api, "deleteTag").mockResolvedValue(undefined);
    const store = createStore();
    await store.dispatch(loadTags(undefined));
    await store.dispatch(deleteTag("g1"));
    expect(store.getState().tags.data).toEqual([]);
  });

  it("surfaces a duplicate name without changing the list", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([TAG]);
    vi.spyOn(api, "createTag").mockRejectedValue(new ApiError("that name already exists", 409));
    const store = createStore();
    await store.dispatch(loadTags(undefined));
    const result = await store.dispatch(createTag({ name: "parsha", name_he: null, color: null }));
    expect(result.type).toBe("tags/create/rejected");
    expect(store.getState().tags.data).toHaveLength(1);
  });

  it("surfaces a failed delete without dropping the tag", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([TAG]);
    vi.spyOn(api, "deleteTag").mockRejectedValue(new ApiError("no tag with that id", 404));
    const store = createStore();
    await store.dispatch(loadTags(undefined));
    await store.dispatch(deleteTag("g1"));
    expect(store.getState().tags.data).toHaveLength(1);
  });

  it("surfaces a failed rename without changing the tag", async () => {
    vi.spyOn(api, "tags").mockResolvedValue([TAG]);
    vi.spyOn(api, "updateTag").mockRejectedValue(new ApiError("that name already exists", 409));
    const store = createStore();
    await store.dispatch(loadTags(undefined));
    await store.dispatch(updateTag({ id: "g1", changes: { name: "mussar" } }));
    expect(store.getState().tags.data[0]?.name).toBe("parsha");
  });
});

describe("toasts", () => {
  it("pushes and dismisses by id", () => {
    const store = createStore();
    store.dispatch(pushToast("Advanced to Jeremiah 47", "success"));
    const [toast] = store.getState().toasts.items;
    expect(toast?.message).toBe("Advanced to Jeremiah 47");
    expect(toast?.tone).toBe("success");
    store.dispatch(dismissToast(toast?.id ?? ""));
    expect(store.getState().toasts.items).toEqual([]);
  });

  it("defaults to the neutral tone", () => {
    const store = createStore();
    store.dispatch(pushToast("Saved"));
    expect(store.getState().toasts.items[0]?.tone).toBe("info");
  });

  it("dismisses only the toast asked for", () => {
    const store = createStore();
    store.dispatch(pushToast("first"));
    store.dispatch(pushToast("second"));
    const first = store.getState().toasts.items[0]?.id ?? "";
    store.dispatch(dismissToast(first));
    expect(store.getState().toasts.items.map((toast) => toast.message)).toEqual(["second"]);
  });
});

describe("correcting a track", () => {
  it("replaces the row a position correction answers with", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([TRACK]);
    vi.spyOn(api, "correctPosition").mockResolvedValue({
      from_ordinal: 121,
      to_ordinal: 120,
      removed_units: 1,
      removed_advances: 0,
      moved: true,
      track: { ...TRACK, actual_ordinal: 120, debt: 3 },
    });
    const store = createStore();
    await store.dispatch(loadTracks(undefined));
    await store.dispatch(
      correctPosition({ trackId: "t1", destination: { toOrdinal: 120 }, confirm: true }),
    );
    expect(store.getState().tracks.data[0]?.actual_ordinal).toBe(120);
  });

  it("leaves other rows alone when a position is corrected", async () => {
    const other: TrackRow = { ...TRACK, id: "t2", name_en: "Ketuvim" };
    vi.spyOn(api, "tracks").mockResolvedValue([TRACK, other]);
    vi.spyOn(api, "correctPosition").mockResolvedValue({
      from_ordinal: 121,
      to_ordinal: 120,
      removed_units: 1,
      removed_advances: 0,
      moved: true,
      track: { ...TRACK, actual_ordinal: 120 },
    });
    const store = createStore();
    await store.dispatch(loadTracks(undefined));
    await store.dispatch(
      correctPosition({ trackId: "t1", destination: { toOrdinal: 120 }, confirm: true }),
    );
    expect(store.getState().tracks.data[1]?.name_en).toBe("Ketuvim");
  });

  it("replaces the row a schedule correction answers with", async () => {
    vi.spyOn(api, "tracks").mockResolvedValue([TRACK]);
    vi.spyOn(api, "correctSchedule").mockResolvedValue({ ...TRACK, debt: 0 });
    const store = createStore();
    await store.dispatch(loadTracks(undefined));
    await store.dispatch(correctSchedule({ trackId: "t1", correction: { startedOn: "2026-08-25" } }));
    expect(store.getState().tracks.data[0]?.debt).toBe(0);
  });

  it("surfaces a refusal rather than swallowing it", async () => {
    vi.spyOn(api, "correctPosition").mockRejectedValue(new ApiError("there is no undo", 422));
    const store = createStore();
    const result = await store.dispatch(
      correctPosition({ trackId: "t1", destination: { toOrdinal: 1 }, confirm: false }),
    );
    expect(result.type).toBe("tracks/correctPosition/rejected");
  });

  it("surfaces a schedule refusal too", async () => {
    vi.spyOn(api, "correctSchedule").mockRejectedValue(new ApiError("not a schedule", 422));
    const store = createStore();
    const result = await store.dispatch(
      correctSchedule({ trackId: "t1", correction: { toOrdinal: 1 } }),
    );
    expect(result.type).toBe("tracks/correctSchedule/rejected");
  });
});

describe("the maintenance slices", () => {
  it("holds the status once it arrives", async () => {
    const status = {
      catalog_seeded: true,
      ledger_seeded: true,
      works: 279,
      stored_units: 432,
      tracks: 20,
      advances: 25,
      ledger_exported_at: null,
      safety_copy_at: null,
    };
    vi.spyOn(api, "maintenance").mockResolvedValue(status);
    const store = createStore();
    await store.dispatch(loadMaintenance(undefined));
    expect(store.getState().maintenance.data).toEqual(status);
  });

  it("surfaces a failure to read the status", async () => {
    vi.spyOn(api, "maintenance").mockRejectedValue(new ApiError("no database", 409));
    const store = createStore();
    await store.dispatch(loadMaintenance(undefined));
    expect(store.getState().maintenance.error).toBe("no database");
    expect(store.getState().maintenance.isConflict).toBe(true);
  });

  it("holds the one job, and null when none has run", async () => {
    vi.spyOn(api, "job").mockResolvedValue(null);
    const store = createStore();
    await store.dispatch(pollJob(undefined));
    expect(store.getState().job.data).toBeNull();
  });

  it("surfaces a failure to poll", async () => {
    vi.spyOn(api, "job").mockRejectedValue(new ApiError("gone", 500));
    const store = createStore();
    await store.dispatch(pollJob(undefined));
    expect(store.getState().job.error).toBe("gone");
  });
});
