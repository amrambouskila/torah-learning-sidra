/**
 * The sentence to show for a failure, whatever shape it arrived in.
 *
 * `unwrap()` on a thunk rejected with `rejectWithValue` throws the *payload*, not an Error, so a
 * bare `instanceof Error` check silently swaps the backend's own explanation for a generic one.
 * That is exactly the information the whole error path exists to preserve.
 */
export function failureMessage(caught: unknown, fallback: string): string {
  if (caught instanceof Error) return caught.message;
  if (typeof caught === "object" && caught !== null && "message" in caught) {
    const { message } = caught;
    if (typeof message === "string" && message !== "") return message;
  }
  return fallback;
}
