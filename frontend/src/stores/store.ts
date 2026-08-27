import { configureStore } from "@reduxjs/toolkit";

import { alignmentSlice } from "./alignmentSlice";
import { chavrusasSlice } from "./chavrusasSlice";
import { jobSlice } from "./jobSlice";
import { maintenanceSlice } from "./maintenanceSlice";
import { paceSlice } from "./paceSlice";
import { sequenceSlice } from "./sequenceSlice";
import { statsSlice } from "./statsSlice";
import { roadmapSlice } from "./roadmapSlice";
import { tagsSlice } from "./tagsSlice";
import { toastSlice } from "./toastSlice";
import { todaySlice } from "./todaySlice";
import { tracksSlice } from "./tracksSlice";

export function createStore() {
  return configureStore({
    reducer: {
      today: todaySlice.reducer,
      tracks: tracksSlice.reducer,
      roadmap: roadmapSlice.reducer,
      chavrusas: chavrusasSlice.reducer,
      tags: tagsSlice.reducer,
      alignment: alignmentSlice.reducer,
      pace: paceSlice.reducer,
      sequence: sequenceSlice.reducer,
      stats: statsSlice.reducer,
      maintenance: maintenanceSlice.reducer,
      job: jobSlice.reducer,
      toasts: toastSlice.reducer,
    },
  });
}

export type AppStore = ReturnType<typeof createStore>;
export type RootState = ReturnType<AppStore["getState"]>;
export type AppDispatch = AppStore["dispatch"];
