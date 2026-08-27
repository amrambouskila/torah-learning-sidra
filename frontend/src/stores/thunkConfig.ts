import { ApiError } from "@/api/ApiError";
import type { FetchFailure } from "@/types/FetchFailure";

/** Every thunk in the app rejects with this shape, so every slice reduces failure identically. */
export interface ThunkConfig {
  rejectValue: FetchFailure;
}

const FALLBACK = "The request failed.";

export function asFailure(error: unknown): FetchFailure {
  // An Error can carry an empty message, and an empty banner says less than no banner at all.
  if (error instanceof ApiError) return { message: error.message || FALLBACK, isConflict: error.isConflict };
  if (error instanceof Error) return { message: error.message || FALLBACK, isConflict: false };
  return { message: FALLBACK, isConflict: false };
}
