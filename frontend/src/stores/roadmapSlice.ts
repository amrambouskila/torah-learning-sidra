import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { RoadmapRow } from "@/types/RoadmapRow";

import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

export const loadRoadmap = createAsyncThunk<readonly RoadmapRow[], string | undefined, ThunkConfig>(
  "roadmap/load",
  async (on, { rejectWithValue }) => {
    try {
      return await api.roadmap(on === undefined ? {} : { on });
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const roadmapSlice = createSlice({
  name: "roadmap",
  initialState: initialAsyncState<readonly RoadmapRow[]>([]),
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, loadRoadmap);
  },
});
