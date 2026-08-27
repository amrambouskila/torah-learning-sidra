import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { PaceRow } from "@/types/PaceRow";

import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

export interface PaceQuery {
  readonly years: number;
  readonly perDay: number;
}

export const loadPace = createAsyncThunk<readonly PaceRow[], PaceQuery, ThunkConfig>(
  "pace/load",
  async ({ years, perDay }, { rejectWithValue }) => {
    try {
      return await api.pace(years, perDay);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const paceSlice = createSlice({
  name: "pace",
  initialState: initialAsyncState<readonly PaceRow[]>([]),
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, loadPace);
  },
});
