import type { ActionReducerMapBuilder, AsyncThunk } from "@reduxjs/toolkit";

import type { AsyncState } from "./AsyncState";
import type { ThunkConfig } from "./thunkConfig";

/**
 * The three cases every fetched resource has, in one place.
 *
 * Six slices need exactly this; writing it out six times is how the pending and rejected branches
 * drift apart until one screen spins forever.
 *
 * Each case returns a new state rather than mutating the draft. The API types are deeply
 * `readonly` — they describe a response, which nothing should edit — and Immer's draft types
 * refuse a readonly array, so replacing the object wholesale is both simpler and truer.
 */
export function attachAsync<TData, TPayload extends TData, Arg>(
  builder: ActionReducerMapBuilder<AsyncState<TData>>,
  thunk: AsyncThunk<TPayload, Arg, ThunkConfig>,
): void {
  builder
    .addCase(thunk.pending, (state) => ({
      ...state,
      status: "loading" as const,
      error: null,
      isConflict: false,
    }))
    .addCase(thunk.fulfilled, (state, action) => ({
      ...state,
      status: "ready" as const,
      data: action.payload,
      error: null,
      isConflict: false,
    }))
    .addCase(thunk.rejected, (state, action) => ({
      ...state,
      status: "failed" as const,
      // A thunk rejected through `rejectWithValue` carries a payload; one that was aborted
      // carries a serialized error instead, and a hand-dispatched action may carry neither.
      error: action.payload?.message ?? action.error.message ?? "The request failed.",
      isConflict: action.payload?.isConflict ?? false,
    }));
}
