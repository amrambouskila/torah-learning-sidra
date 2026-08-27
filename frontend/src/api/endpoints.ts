import type { AdvanceDestination } from "@/types/AdvanceDestination";
import type { AdvanceResult } from "@/types/AdvanceResult";
import type { AlignmentRow } from "@/types/AlignmentRow";
import type { ChavrusaRow } from "@/types/ChavrusaRow";
import type { ExportResult } from "@/types/ExportResult";
import type { JobView } from "@/types/JobView";
import type { MaintenanceStatus } from "@/types/MaintenanceStatus";
import type { CorrectionResult } from "@/types/CorrectionResult";
import type { PaceRow } from "@/types/PaceRow";
import type { RailUnit } from "@/types/RailUnit";
import type { RoadmapRow } from "@/types/RoadmapRow";
import type { ScheduleCorrection } from "@/types/ScheduleCorrection";
import type { SequenceResponse } from "@/types/SequenceResponse";
import type { StatsResponse } from "@/types/StatsResponse";
import type { TagRead } from "@/types/TagRead";
import type { TodayResponse } from "@/types/TodayResponse";
import type { TrackDetail } from "@/types/TrackDetail";
import type { TrackRow } from "@/types/TrackRow";
import type { VerifyResult } from "@/types/VerifyResult";

import { request, requestNoContent } from "./request";

/** `on` pins a request to a civil date; omitted, the server uses today. */
export interface DayQuery {
  readonly on?: string;
}

export const api = {
  today: (query: DayQuery = {}): Promise<TodayResponse> =>
    request<TodayResponse>("/api/today", { params: { on: query.on } }),

  tracks: (query: DayQuery = {}): Promise<readonly TrackRow[]> =>
    request<readonly TrackRow[]>("/api/tracks", { params: { on: query.on } }),

  track: (id: string, query: DayQuery & { readonly radius?: number } = {}): Promise<TrackDetail> =>
    request<TrackDetail>(`/api/tracks/${id}`, { params: { on: query.on, radius: query.radius } }),

  setStart: (id: string, startsOn: string | null, forgive = false): Promise<TrackRow> =>
    request<TrackRow>(`/api/tracks/${id}`, {
      method: "PATCH",
      body: { starts_on: startsOn, forgive },
    }),

  setTrackTags: (id: string, tagIds: readonly string[]): Promise<TrackRow> =>
    request<TrackRow>(`/api/tracks/${id}/tags`, {
      method: "PUT",
      body: { tag_ids: tagIds },
    }),

  rail: (id: string, from: number, to: number, query: DayQuery = {}): Promise<readonly RailUnit[]> =>
    request<readonly RailUnit[]>(`/api/tracks/${id}/rail`, {
      params: { from, to, on: query.on },
    }),

  /** Say where he got to. A ref for anything he typed or picked; an ordinal only from the rail. */
  advance: (
    id: string,
    destination: AdvanceDestination,
    options: { readonly note?: string; readonly occurredOn?: string } = {},
  ): Promise<AdvanceResult> =>
    request<AdvanceResult>(`/api/tracks/${id}/advance`, {
      method: "POST",
      body: {
        ...("toRef" in destination ? { to_ref: destination.toRef } : { to_ordinal: destination.toOrdinal }),
        note: options.note ?? null,
        occurred_on: options.occurredOn ?? null,
      },
    }),

  /**
   * Say where he really is. Backwards only — the server refuses anything ahead, because an
   * endpoint named for correction must never quietly record learning.
   */
  correctPosition: (
    id: string,
    destination: AdvanceDestination,
    confirm: boolean,
  ): Promise<CorrectionResult> =>
    request<CorrectionResult>(`/api/tracks/${id}/position`, {
      method: "PUT",
      body: {
        ...("toRef" in destination ? { to_ref: destination.toRef } : { to_ordinal: destination.toOrdinal }),
        confirm,
      },
    }),

  /** Say what he is supposed to be up to — by the day it started, or by the place itself. */
  correctSchedule: (id: string, correction: ScheduleCorrection): Promise<TrackRow> =>
    request<TrackRow>(`/api/tracks/${id}/schedule`, {
      method: "PUT",
      body:
        "startedOn" in correction
          ? { started_on: correction.startedOn }
          : "toRef" in correction
            ? { to_ref: correction.toRef }
            : { to_ordinal: correction.toOrdinal },
    }),

  pace: (years: number, perDay: number): Promise<readonly PaceRow[]> =>
    request<readonly PaceRow[]>("/api/pace", { params: { years, per_day: perDay } }),

  stats: (windowDays: number): Promise<StatsResponse> =>
    request<StatsResponse>("/api/stats", { params: { window: windowDays } }),

  sequence: (trackId: string): Promise<SequenceResponse> =>
    request<SequenceResponse>(`/api/sequence/${trackId}`),

  roadmap: (query: DayQuery = {}): Promise<readonly RoadmapRow[]> =>
    request<readonly RoadmapRow[]>("/api/roadmap", { params: { on: query.on } }),

  chavrusas: (query: DayQuery = {}): Promise<readonly ChavrusaRow[]> =>
    request<readonly ChavrusaRow[]>("/api/chavrusas", { params: { on: query.on } }),

  tags: (): Promise<readonly TagRead[]> => request<readonly TagRead[]>("/api/tags"),

  createTag: (body: { name: string; name_he: string | null; color: string | null }): Promise<TagRead> =>
    request<TagRead>("/api/tags", { method: "POST", body }),

  updateTag: (
    id: string,
    body: Partial<{ name: string; name_he: string | null; color: string | null }>,
  ): Promise<TagRead> => request<TagRead>(`/api/tags/${id}`, { method: "PATCH", body }),

  deleteTag: (id: string): Promise<void> => requestNoContent(`/api/tags/${id}`, "DELETE"),

  // --- maintenance: the verbs that used to need a terminal ---------------------------------------

  maintenance: (): Promise<MaintenanceStatus> => request<MaintenanceStatus>("/api/maintenance"),

  /** The running job, the last one to finish, or null. One slot, so it needs no id. */
  job: (): Promise<JobView | null> => request<JobView | null>("/api/maintenance/job"),

  exportLedger: (): Promise<ExportResult> =>
    request<ExportResult>("/api/maintenance/export", { method: "POST", body: {} }),

  verifyCatalog: (): Promise<VerifyResult> =>
    request<VerifyResult>("/api/maintenance/verify", { method: "POST", body: {} }),

  seedCatalog: (): Promise<JobView> =>
    request<JobView>("/api/maintenance/seed", { method: "POST", body: {} }),

  fetchCalendar: (start: string, days: number): Promise<JobView> =>
    request<JobView>("/api/maintenance/calendar", { method: "POST", body: { start, days } }),

  refreshSnapshot: (includeLinks: boolean): Promise<JobView> =>
    request<JobView>("/api/maintenance/refresh", { method: "POST", body: { include_links: includeLinks } }),

  /** The one button that can destroy learning, and it exists to undo the one other that can. */
  restoreLedger: (confirm: string): Promise<ExportResult> =>
    request<ExportResult>("/api/maintenance/restore", { method: "POST", body: { confirm } }),

  alignment: (trackId: string, limit?: number): Promise<readonly AlignmentRow[]> =>
    request<readonly AlignmentRow[]>(`/api/alignment/${trackId}`, { params: { limit } }),
} as const;
