import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { request, requestNoContent } from "@/api/request";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("request", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the decoded body", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ ok: true }));
    await expect(request<{ ok: boolean }>("/api/today")).resolves.toEqual({ ok: true });
  });

  it("appends only the params that are set", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse([]));
    await request("/api/tracks", { params: { on: "2026-08-25", radius: undefined } });
    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("/api/tracks?on=2026-08-25");
  });

  it("omits the query string entirely when nothing is set", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse([]));
    await request("/api/tracks", { params: { on: undefined } });
    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("/api/tracks");
  });

  it("sends a JSON body with the right header", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}));
    await request("/api/tags", { method: "POST", body: { name: "parsha" } });
    const init = vi.mocked(fetch).mock.calls[0]?.[1];
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe('{"name":"parsha"}');
    expect(init?.headers).toEqual({ "Content-Type": "application/json" });
  });

  it("carries the backend's own sentence out of a 409", async () => {
    // The failure that matters: a missing calendar span names the command to run.
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ detail: "no calendar snapshot for 2026-08-25; run 'sidra-db calendar'" }, 409),
    );
    await expect(request("/api/today")).rejects.toThrowError(
      /run 'sidra-db calendar'/,
    );
  });

  it("marks a 409 as a conflict and other statuses as not", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "nope" }, 409));
    const conflict = await request("/api/today").catch((error: unknown) => error);
    expect(conflict).toBeInstanceOf(ApiError);
    expect((conflict as ApiError).isConflict).toBe(true);

    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "gone" }, 404));
    const missing = await request("/api/today").catch((error: unknown) => error);
    expect((missing as ApiError).isConflict).toBe(false);
    expect((missing as ApiError).status).toBe(404);
  });

  it("stringifies a structured detail rather than dropping it", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: [{ loc: ["body"], msg: "bad" }] }, 422));
    await expect(request("/api/tags")).rejects.toThrowError(/"msg":"bad"/);
  });

  it("falls back to the status line when the error body is not JSON", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("<html>502</html>", { status: 502 }));
    await expect(request("/api/today")).rejects.toThrowError(/502/);
  });

  it("falls back to the status line when the body is JSON without a detail", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ error: "nope" }, 500));
    await expect(request("/api/today")).rejects.toThrowError(/500/);
  });

  it("lets a network failure through as itself", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(request("/api/today")).rejects.toThrowError(/Failed to fetch/);
  });
});

describe("requestNoContent", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolves on a 204, which carries no body to parse", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    await expect(requestNoContent("/api/tags/abc", "DELETE")).resolves.toBeUndefined();
  });

  it("raises with the detail on failure", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: "no tag with id abc" }, 404));
    await expect(requestNoContent("/api/tags/abc", "DELETE")).rejects.toThrowError(/no tag with id/);
  });
});
