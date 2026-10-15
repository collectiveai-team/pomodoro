import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { makeTimer, okResult } from "./task-fixtures";
import { TimerPanel } from "./timer-panel";

const getMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
    POST: vi.fn(),
  },
}));

vi.mock("@/lib/alarm", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/alarm")>()),
  unlockAlarm: vi.fn(),
}));

const task = { id: "task-1", text: "Escribir informe" };
let current: Record<string, unknown> = makeTimer("Idle");

function timerIn(phase: string, overrides: Record<string, unknown> = {}) {
  return { ...makeTimer(phase, 600), task, ...overrides };
}

beforeEach(() => {
  getMock.mockReset();
  getMock.mockImplementation((path: string) =>
    okResult(path === "/api/v1/timer" ? current : { alarm_enabled: false }),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TimerPanel — Task card", () => {
  it.each(["PomodoroRunning", "PomodoroPaused", "AskingToLog"])(
    "says 'Trabajando en' during %s",
    async (phase) => {
      current = timerIn(phase);
      render(<TimerPanel />);

      expect(await screen.findByText("Trabajando en: Escribir informe")).toBeTruthy();
    },
  );

  it.each(["BreakRunning", "BreakPaused", "ReadyForNext"])(
    "says 'Última tarea' during %s",
    async (phase) => {
      current = timerIn(phase, { break_kind: "short" });
      render(<TimerPanel />);

      expect(await screen.findByText("Última tarea: Escribir informe")).toBeTruthy();
    },
  );

  it("is hidden at rest", async () => {
    current = makeTimer("Idle");
    render(<TimerPanel />);

    await screen.findByText("En reposo");
    expect(screen.queryByText(/Trabajando en|Última tarea/)).toBeNull();
  });

  it("opens the Task detail from its ⓘ with the Task id", async () => {
    current = timerIn("PomodoroRunning");
    const onOpenDetail = vi.fn();
    render(<TimerPanel onOpenDetail={onOpenDetail} />);

    await userEvent.click(
      await screen.findByRole("button", { name: /detalle.*Escribir informe/i }),
    );

    expect(onOpenDetail).toHaveBeenCalledWith("task-1");
  });
});

describe("TimerPanel — phase line", () => {
  it.each([
    ["PomodoroRunning", "Pomodoro"],
    ["PomodoroPaused", "Pomodoro en pausa"],
    ["AskingToLog", "Pomodoro interrumpido"],
    ["BreakRunning", "Break corto"],
    ["BreakPaused", "Break corto en pausa"],
    ["ReadyForNext", "Pomodoro completado — listo para el próximo"],
    ["Idle", "En reposo"],
  ])("labels %s as '%s'", async (phase, label) => {
    current = timerIn(phase, { break_kind: phase.startsWith("Break") ? "short" : null });
    render(<TimerPanel />);

    const line = await screen.findByTestId("phase-line");
    expect(line.textContent).toBe(label);
    expect(line.className).toContain("uppercase");
  });

  it("names a long Break", async () => {
    current = timerIn("BreakRunning", { break_kind: "long" });
    render(<TimerPanel />);

    expect((await screen.findByTestId("phase-line")).textContent).toBe("Break largo");
  });

  it("never says 'descanso'", async () => {
    current = timerIn("BreakRunning", { break_kind: "short" });
    const { container } = render(<TimerPanel />);

    await screen.findByTestId("phase-line");
    expect(container.textContent?.toLowerCase()).not.toContain("descanso");
  });
});

describe("TimerPanel — ring and footer", () => {
  it("renders the clock digits black-weight and tabular", async () => {
    current = timerIn("PomodoroRunning");
    render(<TimerPanel />);

    const digits = await screen.findByTestId("clock-digits");
    expect(digits.className).toContain("font-black");
    expect(digits.className).toContain("tabular");
  });

  it("shows the wordmark in the display serif italic", async () => {
    current = timerIn("PomodoroRunning");
    render(<TimerPanel />);

    const wordmark = await screen.findByText("Pomodoro Collective");
    expect(wordmark.className).toContain("font-display");
    expect(wordmark.className).toContain("italic");
  });

  it.each([
    [0, "Hoy · 0 Pomodoros"],
    [1, "Hoy · 1 Pomodoro"],
    [3, "Hoy · 3 Pomodoros"],
  ])("shows %i completed today as '%s'", async (count, text) => {
    current = timerIn("PomodoroRunning", { pomodoros_completed_today: count });
    render(<TimerPanel />);

    await waitFor(() => expect(screen.getByText(text)).toBeTruthy());
  });
});

describe("TimerPanel — cycle dots", () => {
  it.each([
    ["PomodoroRunning", null, 4, 1],
    ["PomodoroRunning", null, 2, 3],
    ["BreakRunning", "long", 5, 5],
    ["ReadyForNext", "long", 5, 5],
  ])("shows %s/%s with %i left as %i of 5", async (phase, breakKind, left, filled) => {
    current = timerIn(phase, { break_kind: breakKind, pomodoros_until_long_break: left });
    render(<TimerPanel />);

    expect(
      await screen.findByRole("img", { name: `Ciclo: ${filled} de 5 Pomodoros` }),
    ).toBeTruthy();
    expect(screen.queryByText(/Para el Break largo/)).toBeNull();
  });
});
