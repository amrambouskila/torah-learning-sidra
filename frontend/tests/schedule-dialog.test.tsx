/**
 * Correcting what a track is supposed to be up to.
 *
 * The two operands sit side by side because they disagree about the past: moving the day it
 * started leaves the opening debt the ledger was seeded with standing, while naming the place it
 * should have reached restates it. The dialog's whole job is to make him say which.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/ApiError";
import { api } from "@/api/endpoints";
import { ScheduleDialog } from "@/components/ScheduleDialog";
import { ToastStack } from "@/components/ToastStack";
import { TrackScreen } from "@/screens/TrackScreen";
import { createStore } from "@/stores/store";

import { CHUMASH, GEMARA, HADAR, track } from "./fixtures";

function stubRail(): void {
  vi.spyOn(api, "rail").mockImplementation((_id, from, to) =>
    Promise.resolve(
      Array.from({ length: Math.max(0, to - from + 1) }, (_, index) => ({
        ordinal: from + index,
        ref: `Avodah Zarah ${String(from + index)}`,
        work_title_en: "Avodah Zarah",
        work_title_he: "עבודה זרה",
        label_en: String(from + index),
        label_he: "כ״ט",
        sefaria_url: null,
        is_actual: false,
        is_scheduled: false,
      })),
    ),
  );
}

function mountTrack(): void {
  render(
    <Provider store={createStore()}>
      <MemoryRouter initialEntries={["/tracks/t-gemara"]}>
        <Routes>
          <Route path="/tracks/:trackId" element={<TrackScreen />} />
        </Routes>
        <ToastStack />
      </MemoryRouter>
    </Provider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ScheduleDialog", () => {
  it("sends the day it started when that is the operand he answered", async () => {
    stubRail();
    const onConfirm = vi.fn();
    render(<ScheduleDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Started on"), "2026-08-25");
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));

    expect(onConfirm).toHaveBeenCalledWith({ startedOn: "2026-08-25" });
  });

  it("accepts a day in the past, which is the whole point", async () => {
    stubRail();
    const onConfirm = vi.fn();
    render(<ScheduleDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);

    const field = screen.getByLabelText("Started on");
    expect(field).toHaveValue("");
    await userEvent.type(field, "2020-01-01");
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));

    expect(onConfirm).toHaveBeenCalledWith({ startedOn: "2020-01-01" });
  });

  it("sends a picked unit as its ordinal, because an address repeats across sefarim", async () => {
    stubRail();
    const onConfirm = vi.fn();
    render(<ScheduleDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);
    await waitFor(() => {
      expect(api.rail).toHaveBeenCalled();
    });

    await userEvent.type(screen.getByLabelText("Should be at"), "Avodah Zarah 70");
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));

    expect(onConfirm).toHaveBeenCalledWith({ toOrdinal: 70 });
  });

  it("sends anything it does not recognise as a reference", async () => {
    stubRail();
    const onConfirm = vi.fn();
    render(<ScheduleDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Should be at"), "Avodah Zarah 3b");
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));

    expect(onConfirm).toHaveBeenCalledWith({ toRef: "Avodah Zarah 3b" });
  });

  it("fills the target with his current position when he says he is up to date", async () => {
    stubRail();
    const onConfirm = vi.fn();
    render(<ScheduleDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /I'm up to date/ }));
    expect(screen.getByLabelText("Should be at")).toHaveValue("Avodah Zarah 28b");

    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));
    expect(onConfirm).toHaveBeenCalledWith({ toRef: "Avodah Zarah 28b" });
  });

  it("offers no shortcut on a track he has never opened", () => {
    stubRail();
    render(
      <ScheduleDialog track={track({ ...GEMARA, at: null })} onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: /I'm up to date/ })).not.toBeInTheDocument();
  });

  it("sends exactly one operand, never both", async () => {
    stubRail();
    const onConfirm = vi.fn();
    render(<ScheduleDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Started on"), "2026-08-25");
    await userEvent.type(screen.getByLabelText("Should be at"), "Avodah Zarah 70");
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));

    // Typing into the target moved the answer onto it; the date is not sent alongside.
    expect(onConfirm).toHaveBeenCalledWith({ toOrdinal: 70 });
  });

  it("lets him switch back to the day by choosing it again", async () => {
    stubRail();
    const onConfirm = vi.fn();
    render(<ScheduleDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Started on"), "2026-08-25");
    await userEvent.type(screen.getByLabelText("Should be at"), "Avodah Zarah 70");
    await userEvent.click(screen.getByRole("radio", { name: "It started on" }));
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));

    expect(onConfirm).toHaveBeenCalledWith({ startedOn: "2026-08-25" });
  });

  it("takes the target radio as the answer even before he types into it", async () => {
    // Choosing the operand and filling it in are two gestures, and either order must work.
    stubRail();
    const onConfirm = vi.fn();
    render(<ScheduleDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);

    await userEvent.click(screen.getByRole("radio", { name: "It should be at" }));
    expect(screen.getByRole("button", { name: "Set schedule" })).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Should be at"), "38b");
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));
    expect(onConfirm).toHaveBeenCalledWith({ toRef: "38b" });
  });

  it("refuses to send nothing", () => {
    stubRail();
    render(<ScheduleDialog track={GEMARA} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Set schedule" })).toBeDisabled();
  });

  it("can be dismissed", async () => {
    stubRail();
    const onCancel = vi.fn();
    render(<ScheduleDialog track={GEMARA} onConfirm={vi.fn()} onCancel={onCancel} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("says what a day is worth on a parsha track", () => {
    stubRail();
    render(<ScheduleDialog track={CHUMASH} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/one day is 1 aliyah here, 2 in a combined week/)).toBeInTheDocument();
  });

  it("carries on without the list when the rail cannot be fetched", async () => {
    vi.spyOn(api, "rail").mockRejectedValue(new ApiError("no rail", 500));
    const onConfirm = vi.fn();
    render(<ScheduleDialog track={GEMARA} onConfirm={onConfirm} onCancel={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Should be at"), "38b");
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));

    expect(onConfirm).toHaveBeenCalledWith({ toRef: "38b" });
  });

  it("falls back to the track name when there is no scheduled position", () => {
    stubRail();
    render(
      <ScheduleDialog
        track={track({ ...GEMARA, scheduled_at: null })}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText("Gemara")).toBeInTheDocument();
  });
});

describe("the Track screen's schedule button", () => {
  it("corrects the schedule and says where it landed", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "correctSchedule").mockResolvedValue(
      track({ ...GEMARA, debt: 0, scheduled_at: GEMARA.at }),
    );
    mountTrack();

    await userEvent.click(await screen.findByRole("button", { name: "Schedule" }));
    await userEvent.type(screen.getByLabelText("Started on"), "2026-08-25");
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));

    await waitFor(() => {
      expect(api.correctSchedule).toHaveBeenCalledWith("t-gemara", { startedOn: "2026-08-25" });
    });
    expect(await screen.findByText(/Scheduled to Avodah Zarah 28b/)).toBeInTheDocument();
  });

  it("surfaces a refusal from the server", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "correctSchedule").mockRejectedValue(
      new ApiError("that would put the schedule's origin before its first unit", 422),
    );
    mountTrack();

    await userEvent.click(await screen.findByRole("button", { name: "Schedule" }));
    await userEvent.type(screen.getByLabelText("Started on"), "2026-08-25");
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));

    expect(
      await screen.findByText("that would put the schedule's origin before its first unit"),
    ).toBeInTheDocument();
  });

  it("falls back when the corrected track has no scheduled position", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "correctSchedule").mockResolvedValue(track({ ...GEMARA, scheduled_at: null }));
    mountTrack();

    await userEvent.click(await screen.findByRole("button", { name: "Schedule" }));
    await userEvent.type(screen.getByLabelText("Started on"), "2026-08-25");
    await userEvent.click(screen.getByRole("button", { name: "Set schedule" }));

    expect(await screen.findByText(/Scheduled to the start/)).toBeInTheDocument();
  });

  it("can be dismissed without changing anything", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: GEMARA, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    vi.spyOn(api, "correctSchedule");
    mountTrack();

    await userEvent.click(await screen.findByRole("button", { name: "Schedule" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(api.correctSchedule).not.toHaveBeenCalled();
  });

  it("is not offered on a chavrusa track, which has no schedule at all", async () => {
    vi.spyOn(api, "track").mockResolvedValue({ track: HADAR, rail: [], rail_from: 0, rail_to: 0 });
    stubRail();
    mountTrack();

    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("button", { name: "Schedule" })).not.toBeInTheDocument();
  });
});
