import { Provider } from "react-redux";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { useMemo, type ReactElement } from "react";

import { Sidebar } from "@/components/Sidebar";
import { ToastStack } from "@/components/ToastStack";
import { AlignmentScreen } from "@/screens/AlignmentScreen";
import { ChavrusasScreen } from "@/screens/ChavrusasScreen";
import { PaceScreen } from "@/screens/PaceScreen";
import { SequenceScreen } from "@/screens/SequenceScreen";
import { StatsScreen } from "@/screens/StatsScreen";
import { RoadmapScreen } from "@/screens/RoadmapScreen";
import { MaintenanceScreen } from "@/screens/MaintenanceScreen";
import { TagsScreen } from "@/screens/TagsScreen";
import { TodayScreen } from "@/screens/TodayScreen";
import { TrackScreen } from "@/screens/TrackScreen";
import { createStore, type AppStore } from "@/stores/store";

interface AppProps {
  /** Tests hand in their own store; the app makes one. */
  readonly store?: AppStore;
}

export function App({ store }: AppProps = {}): ReactElement {
  const resolved = useMemo(() => store ?? createStore(), [store]);
  return (
    <Provider store={resolved}>
      <BrowserRouter>
        <div className="app">
          <Sidebar />
          <main className="main">
            <Routes>
              <Route path="/" element={<TodayScreen />} />
              <Route path="/tracks/:trackId" element={<TrackScreen />} />
              <Route path="/roadmap" element={<RoadmapScreen />} />
              <Route path="/pace" element={<PaceScreen />} />
              <Route path="/stats" element={<StatsScreen />} />
              <Route path="/sequence" element={<SequenceScreen />} />
              <Route path="/chavrusas" element={<ChavrusasScreen />} />
              <Route path="/alignment" element={<AlignmentScreen />} />
              <Route path="/tags" element={<TagsScreen />} />
              <Route path="/maintenance" element={<MaintenanceScreen />} />
            </Routes>
          </main>
          <ToastStack />
        </div>
      </BrowserRouter>
    </Provider>
  );
}
