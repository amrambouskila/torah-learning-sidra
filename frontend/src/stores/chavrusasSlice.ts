import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { ChavrusaRow } from "@/types/ChavrusaRow";

import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

export const loadChavrusas = createAsyncThunk<readonly ChavrusaRow[], string | undefined, ThunkConfig>(
  "chavrusas/load",
  async (on, { rejectWithValue }) => {
    try {
      return await api.chavrusas(on === undefined ? {} : { on });
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const chavrusasSlice = createSlice({
  name: "chavrusas",
  initialState: initialAsyncState<readonly ChavrusaRow[]>([]),
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, loadChavrusas);
  },
});
