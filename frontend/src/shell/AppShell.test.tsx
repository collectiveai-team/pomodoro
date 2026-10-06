// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { type ReactNode, useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";

/**
 * Children are replaced with tracked stand-ins so this test exercises only
 * AppShell's own mount/unmount wiring, not the real tabs' fetch-on-mount
 * behavior (that belongs to each tab's own tests).
 */
const mountEvents: string[] = [];

function trackedTab(name: string) {
  return function TrackedTab() {
    useEffect(() => {
      mountEvents.push(`mount:${name}`);
      return () => {
        mountEvents.push(`unmount:${name}`);
      };
    }, []);
    return <div data-testid={`tab-${name}`}>{name}</div>;
  };
}

vi.mock("@/src/tasks/ActiveTab", () => ({ ActiveTab: trackedTab("active") }));
vi.mock("@/src/tasks/ArchivedTab", () => ({
  ArchivedTab: trackedTab("archived"),
}));
vi.mock("@/src/history/HistoryTab", () => ({
  HistoryTab: trackedTab("history"),
}));
vi.mock("@/src/timer/TimerPanel", () => ({
  TimerPanel: () => <div>timer</div>,
}));
vi.mock("@/src/timer/TimerEngineProvider", () => ({
  TimerEngineProvider: ({ children }: { children: ReactNode }) => children,
}));
vi.mock("@/src/account/AccountMenu", () => ({
  AccountMenu: () => <div>account</div>,
}));

afterEach(() => {
  cleanup();
  mountEvents.length = 0;
});

describe("AppShell", () => {
  it("mounts only the selected tab and unmounts the previous one on switch", () => {
    render(<AppShell />);

    expect(screen.getByTestId("tab-active")).toBeTruthy();
    expect(screen.queryByTestId("tab-archived")).toBeNull();
    expect(screen.queryByTestId("tab-history")).toBeNull();
    expect(mountEvents).toEqual(["mount:active"]);

    fireEvent.click(screen.getByRole("button", { name: "Archivadas" }));

    expect(screen.queryByTestId("tab-active")).toBeNull();
    expect(screen.getByTestId("tab-archived")).toBeTruthy();
    expect(mountEvents).toEqual([
      "mount:active",
      "unmount:active",
      "mount:archived",
    ]);

    fireEvent.click(screen.getByRole("button", { name: "Activas" }));

    expect(screen.queryByTestId("tab-archived")).toBeNull();
    expect(screen.getByTestId("tab-active")).toBeTruthy();
    expect(mountEvents).toEqual([
      "mount:active",
      "unmount:active",
      "mount:archived",
      "unmount:archived",
      "mount:active",
    ]);
  });
});
