import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/api/endpoints";
import type { RailUnit } from "@/types/RailUnit";

export const ROW_HEIGHT = 34;
const OVERSCAN = 8;
/** One fetch covers several screenfuls, so ordinary scrolling does not make a request per row. */
const CHUNK = 100;

export interface RailWindow {
  readonly first: number;
  readonly last: number;
  readonly units: readonly RailUnit[];
  readonly error: string | null;
}

export function visibleSpan(
  scrollTop: number,
  viewport: number,
  total: number,
): { first: number; last: number } {
  const first = Math.max(1, Math.floor(scrollTop / ROW_HEIGHT) + 1 - OVERSCAN);
  const rows = Math.ceil(viewport / ROW_HEIGHT) + OVERSCAN * 2;
  return { first, last: Math.min(total, first + rows) };
}

/** The chunk boundaries covering a span, so repeated scrolling reuses what is already fetched. */
export function chunksFor(first: number, last: number): number[] {
  const chunks: number[] = [];
  const start = Math.floor((first - 1) / CHUNK);
  const end = Math.floor((last - 1) / CHUNK);
  for (let index = start; index <= end; index += 1) chunks.push(index);
  return chunks;
}

/**
 * Fetches the rail in chunks as it scrolls into view.
 *
 * The Mishneh Torah chavrusa tracks are 15,143 halachos. Asking for the whole spine would be the
 * heaviest response in the app and would then need 15,143 DOM nodes to render it.
 */
export function useRailWindow(trackId: string, total: number, scrollTop: number, viewport: number): RailWindow {
  const cache = useRef(new Map<number, readonly RailUnit[]>());
  const inFlight = useRef(new Set<number>());
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const { first, last } = visibleSpan(scrollTop, viewport, total);

  const fetchChunk = useCallback(
    async (chunk: number): Promise<void> => {
      if (cache.current.has(chunk) || inFlight.current.has(chunk)) return;
      inFlight.current.add(chunk);
      const from = chunk * CHUNK + 1;
      try {
        const units = await api.rail(trackId, from, from + CHUNK - 1);
        cache.current.set(chunk, units);
        setVersion((current) => current + 1);
        setError(null);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "The rail could not be loaded.");
      } finally {
        inFlight.current.delete(chunk);
      }
    },
    [trackId],
  );

  useEffect(() => {
    cache.current.clear();
    inFlight.current.clear();
    setVersion(0);
  }, [trackId]);

  useEffect(() => {
    if (total === 0) return;
    for (const chunk of chunksFor(first, last)) void fetchChunk(chunk);
  }, [fetchChunk, first, last, total]);

  const units: RailUnit[] = [];
  for (const chunk of chunksFor(first, last)) {
    for (const unit of cache.current.get(chunk) ?? []) {
      if (unit.ordinal >= first && unit.ordinal <= last) units.push(unit);
    }
  }
  units.sort((left, right) => left.ordinal - right.ordinal);

  // `version` is read so a resolved fetch re-renders; the units themselves come from the cache.
  void version;
  return { first, last, units, error };
}
