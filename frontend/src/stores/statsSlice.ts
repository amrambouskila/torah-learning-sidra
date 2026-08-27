import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { StatsResponse } from "@/types/StatsResponse";

import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

export const loadStats = createAsyncThunk<StatsResponse, number, ThunkConfig>(
  "stats/load",
  async (windowDays, { rejectWithValue }) => {
    try {
      return await api.stats(windowDays);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const statsSlice = createSlice({
  name: "stats",
  initialState: initialAsyncState<StatsResponse | null>(null),
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, loadStats);
  },
});
