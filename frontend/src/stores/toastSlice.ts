import { createSlice, nanoid, type PayloadAction } from "@reduxjs/toolkit";

export type ToastTone = "info" | "success" | "failure";

export interface Toast {
  readonly id: string;
  readonly message: string;
  readonly tone: ToastTone;
}

interface ToastState {
  readonly items: readonly Toast[];
}

const initialState: ToastState = { items: [] };

export const toastSlice = createSlice({
  name: "toasts",
  initialState,
  reducers: {
    pushToast: {
      reducer: (state, action: PayloadAction<Toast>) => ({
        items: [...state.items, action.payload],
      }),
      prepare: (message: string, tone: ToastTone = "info") => ({
        payload: { id: nanoid(), message, tone },
      }),
    },
    dismissToast: (state, action: PayloadAction<string>) => ({
      items: state.items.filter((toast) => toast.id !== action.payload),
    }),
  },
});

export const { pushToast, dismissToast } = toastSlice.actions;
