import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { TodayResponse } from "@/types/TodayResponse";

import type { AsyncState } from "./AsyncState";
import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

export const loadToday = createAsyncThunk<TodayResponse, string | undefined, ThunkConfig>(
  "today/load",
  async (on, { rejectWithValue }) => {
    try {
      return await api.today(on === undefined ? {} : { on });
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

const initial: AsyncState<TodayResponse | null> = initialAsyncState<TodayResponse | null>(null);

export const todaySlice = createSlice({
  name: "today",
  initialState: initial,
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, loadToday);
  },
});
