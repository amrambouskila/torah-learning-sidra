import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";

import { api } from "@/api/endpoints";
import type { TagRead } from "@/types/TagRead";

import { initialAsyncState } from "./AsyncState";
import { attachAsync } from "./attachAsync";
import { asFailure, type ThunkConfig } from "./thunkConfig";

export interface TagDraft {
  readonly name: string;
  readonly name_he: string | null;
  readonly color: string | null;
}

export const loadTags = createAsyncThunk<readonly TagRead[], undefined, ThunkConfig>(
  "tags/load",
  async (_arg, { rejectWithValue }) => {
    try {
      return await api.tags();
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const createTag = createAsyncThunk<TagRead, TagDraft, ThunkConfig>(
  "tags/create",
  async (draft, { rejectWithValue }) => {
    try {
      return await api.createTag(draft);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const updateTag = createAsyncThunk<TagRead, { id: string; changes: Partial<TagDraft> }, ThunkConfig>(
  "tags/update",
  async ({ id, changes }, { rejectWithValue }) => {
    try {
      return await api.updateTag(id, changes);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const deleteTag = createAsyncThunk<string, string, ThunkConfig>(
  "tags/delete",
  async (id, { rejectWithValue }) => {
    try {
      await api.deleteTag(id);
      return id;
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

function byName(left: TagRead, right: TagRead): number {
  return left.name.localeCompare(right.name);
}

export const tagsSlice = createSlice({
  name: "tags",
  initialState: initialAsyncState<readonly TagRead[]>([]),
  reducers: {},
  extraReducers: (builder) => {
    attachAsync(builder, loadTags);
    builder
      .addCase(createTag.fulfilled, (state, action) => ({
        ...state,
        data: [...state.data, action.payload].sort(byName),
      }))
      .addCase(updateTag.fulfilled, (state, action) => ({
        ...state,
        data: state.data.map((tag) => (tag.id === action.payload.id ? action.payload : tag)).sort(byName),
      }))
      .addCase(deleteTag.fulfilled, (state, action) => ({
        ...state,
        data: state.data.filter((tag) => tag.id !== action.payload),
      }));
  },
});
