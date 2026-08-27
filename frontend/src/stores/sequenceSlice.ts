import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { SequenceResponse } from "@/types/SequenceResponse";

import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

export const loadSequence = createAsyncThunk<SequenceResponse, string, ThunkConfig>(
  "sequence/load",
  async (trackId, { rejectWithValue }) => {
    try {
      return await api.sequence(trackId);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const sequenceSlice = createSlice({
  name: "sequence",
  initialState: initialAsyncState<SequenceResponse | null>(null),
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, loadSequence);
  },
});
