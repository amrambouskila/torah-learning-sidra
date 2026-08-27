import { ApiError } from "./ApiError";

interface RequestOptions {
  readonly method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  readonly body?: unknown;
  readonly params?: Readonly<Record<string, string | number | undefined>>;
}

function withParams(path: string, params: RequestOptions["params"]): string {
  if (params === undefined) return path;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const query = search.toString();
  return query === "" ? path : `${path}?${query}`;
}

async function detailOf(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.json();
    if (typeof payload === "object" && payload !== null && "detail" in payload) {
      const { detail } = payload;
      if (typeof detail === "string") return detail;
      return JSON.stringify(detail);
    }
  } catch {
    // A non-JSON error body is normal for a proxy failure; fall through to the status line.
  }
  return `${String(response.status)} ${response.statusText}`;
}

/** One fetch wrapper, so every screen surfaces the same errors the same way. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, params } = options;
  // `exactOptionalPropertyTypes` refuses an explicit `undefined` for an optional field, so the
  // body-carrying keys are spread in only when there is a body.
  const init: RequestInit =
    body === undefined
      ? { method }
      : { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(withParams(path, params), init);

  if (!response.ok) throw new ApiError(await detailOf(response), response.status);
  return (await response.json()) as T;
}

/** A 204 carries no body, so parsing one as JSON would throw on an empty string. */
export async function requestNoContent(path: string, method: "DELETE" | "POST"): Promise<void> {
  const response = await fetch(path, { method });
  if (!response.ok) throw new ApiError(await detailOf(response), response.status);
}
