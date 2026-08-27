import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { AdvanceDestination } from "@/types/AdvanceDestination";
import type { AdvanceResult } from "@/types/AdvanceResult";
import type { CorrectionResult } from "@/types/CorrectionResult";
import type { ScheduleCorrection } from "@/types/ScheduleCorrection";
import type { TrackRow } from "@/types/TrackRow";

import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

export interface AdvanceRequest {
  readonly trackId: string;
  readonly destination: AdvanceDestination;
  readonly note?: string;
}

export interface SetStartRequest {
  readonly trackId: string;
  readonly startsOn: string | null;
  /** Acknowledge that this clears a backlog the track has genuinely accrued. */
  readonly forgive?: boolean;
}

export const loadTracks = createAsyncThunk<readonly TrackRow[], string | undefined, ThunkConfig>(
  "tracks/load",
  async (on, { rejectWithValue }) => {
    try {
      return await api.tracks(on === undefined ? {} : { on });
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const advanceTrack = createAsyncThunk<AdvanceResult, AdvanceRequest, ThunkConfig>(
  "tracks/advance",
  async ({ trackId, destination, note }, { rejectWithValue }) => {
    try {
      return await api.advance(trackId, destination, note === undefined ? {} : { note });
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export interface SetTagsRequest {
  readonly trackId: string;
  /** The complete set the track should wear, not a change to it. */
  readonly tagIds: readonly string[];
}

export const setTrackTags = createAsyncThunk<TrackRow, SetTagsRequest, ThunkConfig>(
  "tracks/setTags",
  async ({ trackId, tagIds }, { rejectWithValue }) => {
    try {
      return await api.setTrackTags(trackId, tagIds);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const setTrackStart = createAsyncThunk<TrackRow, SetStartRequest, ThunkConfig>(
  "tracks/setStart",
  async ({ trackId, startsOn, forgive }, { rejectWithValue }) => {
    try {
      return await api.setStart(trackId, startsOn, forgive ?? false);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export interface CorrectPositionRequest {
  readonly trackId: string;
  readonly destination: AdvanceDestination;
  /** Acknowledge that this deletes recorded learning. There is no undo. */
  readonly confirm: boolean;
}

export interface CorrectScheduleRequest {
  readonly trackId: string;
  readonly correction: ScheduleCorrection;
}

export const correctPosition = createAsyncThunk<CorrectionResult, CorrectPositionRequest, ThunkConfig>(
  "tracks/correctPosition",
  async ({ trackId, destination, confirm }, { rejectWithValue }) => {
    try {
      return await api.correctPosition(trackId, destination, confirm);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const correctSchedule = createAsyncThunk<TrackRow, CorrectScheduleRequest, ThunkConfig>(
  "tracks/correctSchedule",
  async ({ trackId, correction }, { rejectWithValue }) => {
    try {
      return await api.correctSchedule(trackId, correction);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const tracksSlice = createSlice({
  name: "tracks",
  initialState: initialAsyncState<readonly TrackRow[]>([]),
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, loadTracks);
    // An advance answers with the track as it now stands, so the row updates without a refetch.
    builder.addCase(advanceTrack.fulfilled, (state, action) => {
      const updated = action.payload.track;
      return { ...state, data: state.data.map((row) => (row.id === updated.id ? updated : row)) };
    });
    // A start date is answered with the recomputed row, because rebasing moves the debt.
    builder.addCase(setTrackStart.fulfilled, (state, action) => ({
      ...state,
      data: state.data.map((row) => (row.id === action.payload.id ? action.payload : row)),
    }));
    // A correction answers with the track as it now stands, for the same reason an advance does.
    builder.addCase(correctPosition.fulfilled, (state, action) => {
      const updated = action.payload.track;
      return { ...state, data: state.data.map((row) => (row.id === updated.id ? updated : row)) };
    });
    builder.addCase(correctSchedule.fulfilled, (state, action) => ({
      ...state,
      data: state.data.map((row) => (row.id === action.payload.id ? action.payload : row)),
    }));
  },
});
