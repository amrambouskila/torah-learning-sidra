import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/api/endpoints";

function ok(body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function calledUrl(): string {
  const [url] = vi.mocked(fetch).mock.calls[0] ?? [];
  return typeof url === "string" ? url : "";
}

/** The request body as the object it was serialised from. */
function calledBody(): unknown {
  const body = vi.mocked(fetch).mock.calls[0]?.[1]?.body;
  return typeof body === "string" ? JSON.parse(body) : null;
}

describe("the endpoint surface", () => {
  beforeEach(() => {
    // A Response body can be read once, so each call needs its own rather than a shared one.
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(ok())));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads Today, with and without a pinned day", async () => {
    await api.today();
    expect(calledUrl()).toBe("/api/today");
    vi.mocked(fetch).mockClear();
    await api.today({ on: "2026-08-25" });
    expect(calledUrl()).toBe("/api/today?on=2026-08-25");
  });

  it("reads the track list", async () => {
    await api.tracks({ on: "2026-08-25" });
    expect(calledUrl()).toBe("/api/tracks?on=2026-08-25");
  });

  it("reads one track, with a rail radius", async () => {
    await api.track("t1", { radius: 0 });
    expect(calledUrl()).toBe("/api/tracks/t1?radius=0");
  });

  it("reads one track with no options at all", async () => {
    await api.track("t1");
    expect(calledUrl()).toBe("/api/tracks/t1");
  });

  it("reads a rail span", async () => {
    await api.rail("t1", 101, 200);
    expect(calledUrl()).toBe("/api/tracks/t1/rail?from=101&to=200");
  });

  it("reads a rail span pinned to a day", async () => {
    await api.rail("t1", 1, 10, { on: "2026-08-25" });
    expect(calledUrl()).toBe("/api/tracks/t1/rail?from=1&to=10&on=2026-08-25");
  });

  it("posts an advance with an absolute ordinal", async () => {
    // Absolute, so a retried request is a no-op rather than a double count.
    await api.advance("t1", { toOrdinal: 123 });
    const init = vi.mocked(fetch).mock.calls[0]?.[1];
    expect(calledUrl()).toBe("/api/tracks/t1/advance");
    expect(init?.method).toBe("POST");
    expect(calledBody()).toEqual({ to_ordinal: 123, note: null, occurred_on: null });
  });

  it("posts an advance by reference, which is how a person says it", async () => {
    await api.advance("t1", { toRef: "5:7" });
    expect(calledBody()).toEqual({ to_ref: "5:7", note: null, occurred_on: null });
  });

  it("posts an advance carrying a note and a date", async () => {
    await api.advance("t1", { toOrdinal: 123 }, { note: "on the train", occurredOn: "2026-08-24" });
    expect(calledBody()).toEqual({ to_ordinal: 123, note: "on the train", occurred_on: "2026-08-24" });
  });

  it("reads the roadmap and the chavrusas", async () => {
    await api.roadmap();
    expect(calledUrl()).toBe("/api/roadmap");
    vi.mocked(fetch).mockClear();
    await api.chavrusas({ on: "2026-08-25" });
    expect(calledUrl()).toBe("/api/chavrusas?on=2026-08-25");
  });

  it("reads the tags", async () => {
    await api.tags();
    expect(calledUrl()).toBe("/api/tags");
  });

  it("creates, renames and deletes a tag", async () => {
    await api.createTag({ name: "mussar", name_he: null, color: null });
    expect(vi.mocked(fetch).mock.calls[0]?.[1]?.method).toBe("POST");

    vi.mocked(fetch).mockClear();
    await api.updateTag("g1", { name: "parashah" });
    expect(calledUrl()).toBe("/api/tags/g1");
    expect(vi.mocked(fetch).mock.calls[0]?.[1]?.method).toBe("PATCH");

    vi.mocked(fetch).mockClear();
    vi.mocked(fetch).mockImplementation(() => Promise.resolve(new Response(null, { status: 204 })));
    await api.deleteTag("g1");
    expect(vi.mocked(fetch).mock.calls[0]?.[1]?.method).toBe("DELETE");
  });

  it("reads the alignment, with and without a cap", async () => {
    await api.alignment("t1");
    expect(calledUrl()).toBe("/api/alignment/t1");
    vi.mocked(fetch).mockClear();
    await api.alignment("t1", 5);
    expect(calledUrl()).toBe("/api/alignment/t1?limit=5");
  });
});

describe("the start-date endpoint", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(ok())));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("patches a start date onto a track", async () => {
    await api.setStart("t1", "2026-09-08");
    expect(calledUrl()).toBe("/api/tracks/t1");
    expect(vi.mocked(fetch).mock.calls[0]?.[1]?.method).toBe("PATCH");
    expect(calledBody()).toEqual({ starts_on: "2026-09-08", forgive: false });
  });

  it("clears one with an explicit null", async () => {
    await api.setStart("t1", null);
    expect(calledBody()).toEqual({ starts_on: null, forgive: false });
  });

  it("carries the acknowledgement when a backlog is being cleared", async () => {
    await api.setStart("t1", "2026-09-08", true);
    expect(calledBody()).toEqual({ starts_on: "2026-09-08", forgive: true });
  });
});

describe("the pace endpoint", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(ok())));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends both knobs", async () => {
    await api.pace(3, 5);
    expect(calledUrl()).toBe("/api/pace?years=3&per_day=5");
  });
});

describe("the stats endpoint", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(ok())));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the window it was asked for", async () => {
    await api.stats(90);
    expect(calledUrl()).toBe("/api/stats?window=90");
  });
});

describe("the track tags endpoint", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(ok())));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("puts the whole set", async () => {
    await api.setTrackTags("t1", ["tag-a", "tag-b"]);
    expect(calledUrl()).toBe("/api/tracks/t1/tags");
    const [, init] = (globalThis.fetch as unknown as { mock: { calls: [string, RequestInit][] } }).mock
      .calls[0] as [string, RequestInit];
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ tag_ids: ["tag-a", "tag-b"] });
  });
});

describe("the sequence endpoint", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(ok())));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("asks for one track's sequence", async () => {
    await api.sequence("t-jacob");
    expect(calledUrl()).toBe("/api/sequence/t-jacob");
  });
});

describe("the correction endpoints", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(ok())));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("puts a position correction by ordinal, carrying the acknowledgement", async () => {
    await api.correctPosition("t1", { toOrdinal: 262 }, true);
    expect(calledUrl()).toBe("/api/tracks/t1/position");
    expect(vi.mocked(fetch).mock.calls[0]?.[1]?.method).toBe("PUT");
    expect(calledBody()).toEqual({ to_ordinal: 262, confirm: true });
  });

  it("puts a position correction by reference, unconfirmed", async () => {
    await api.correctPosition("t1", { toRef: "Jeremiah 49" }, false);
    expect(calledBody()).toEqual({ to_ref: "Jeremiah 49", confirm: false });
  });

  it("puts a schedule correction naming the day it started", async () => {
    await api.correctSchedule("t1", { startedOn: "2026-08-25" });
    expect(calledUrl()).toBe("/api/tracks/t1/schedule");
    expect(vi.mocked(fetch).mock.calls[0]?.[1]?.method).toBe("PUT");
    expect(calledBody()).toEqual({ started_on: "2026-08-25" });
  });

  it("puts a schedule correction naming the target as an ordinal", async () => {
    await api.correctSchedule("t1", { toOrdinal: 262 });
    expect(calledBody()).toEqual({ to_ordinal: 262 });
  });

  it("puts a schedule correction naming the target as a reference", async () => {
    await api.correctSchedule("t1", { toRef: "Jeremiah 49" });
    expect(calledBody()).toEqual({ to_ref: "Jeremiah 49" });
  });
});

describe("the maintenance endpoints", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(ok())));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads the status and the one job slot", async () => {
    await api.maintenance();
    expect(calledUrl()).toBe("/api/maintenance");
    vi.mocked(fetch).mockClear();
    await api.job();
    expect(calledUrl()).toBe("/api/maintenance/job");
  });

  it("posts the two fast verbs", async () => {
    await api.exportLedger();
    expect(calledUrl()).toBe("/api/maintenance/export");
    expect(vi.mocked(fetch).mock.calls[0]?.[1]?.method).toBe("POST");
    vi.mocked(fetch).mockClear();
    await api.verifyCatalog();
    expect(calledUrl()).toBe("/api/maintenance/verify");
  });

  it("starts a catalog rebuild", async () => {
    await api.seedCatalog();
    expect(calledUrl()).toBe("/api/maintenance/seed");
    expect(vi.mocked(fetch).mock.calls[0]?.[1]?.method).toBe("POST");
  });

  it("sends the calendar span it was given", async () => {
    await api.fetchCalendar("2026-10-01", 400);
    expect(calledUrl()).toBe("/api/maintenance/calendar");
    expect(calledBody()).toEqual({ start: "2026-10-01", days: 400 });
  });

  it("sends whether the crawl should pull the links", async () => {
    await api.refreshSnapshot(false);
    expect(calledUrl()).toBe("/api/maintenance/refresh");
    expect(calledBody()).toEqual({ include_links: false });
  });

  it("sends the typed word when restoring", async () => {
    await api.restoreLedger("RESTORE");
    expect(calledUrl()).toBe("/api/maintenance/restore");
    expect(calledBody()).toEqual({ confirm: "RESTORE" });
  });
});
