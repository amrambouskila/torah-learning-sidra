import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { MaintenanceStatus } from "@/types/MaintenanceStatus";

import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

export const loadMaintenance = createAsyncThunk<MaintenanceStatus | null, undefined, ThunkConfig>(
  "maintenance/load",
  async (_, { rejectWithValue }) => {
    try {
      return await api.maintenance();
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const maintenanceSlice = createSlice({
  name: "maintenance",
  initialState: initialAsyncState<MaintenanceStatus | null>(null),
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, loadMaintenance);
  },
});
