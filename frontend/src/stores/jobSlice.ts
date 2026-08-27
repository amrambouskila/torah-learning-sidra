import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { JobView } from "@/types/JobView";

import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

/**
 * The one job slot.
 *
 * Polled on a timer while something is in flight, and kept apart from the maintenance counts
 * because those do not change until the job ends — refetching them every second would be asking
 * the database six questions to watch a progress bar move.
 */
export const pollJob = createAsyncThunk<JobView | null, undefined, ThunkConfig>(
  "job/poll",
  async (_, { rejectWithValue }) => {
    try {
      return await api.job();
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const jobSlice = createSlice({
  name: "job",
  initialState: initialAsyncState<JobView | null>(null),
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, pollJob);
  },
});
