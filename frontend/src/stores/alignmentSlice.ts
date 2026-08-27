import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { AlignmentRow } from "@/types/AlignmentRow";

import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

export const loadAlignment = createAsyncThunk<readonly AlignmentRow[], string, ThunkConfig>(
  "alignment/load",
  async (trackId, { rejectWithValue }) => {
    try {
      return await api.alignment(trackId);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const alignmentSlice = createSlice({
  name: "alignment",
  initialState: initialAsyncState<readonly AlignmentRow[]>([]),
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, loadAlignment);
  },
});
