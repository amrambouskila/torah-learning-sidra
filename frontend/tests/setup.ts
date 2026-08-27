/**
 * Vitest does NOT auto-cleanup the way Jest does. Without this, component tests leak DOM state
 * between cases and a query that should find one element finds three.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
