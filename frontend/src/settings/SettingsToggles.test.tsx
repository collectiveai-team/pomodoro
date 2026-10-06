// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SettingsToggles } from "./SettingsToggles";

afterEach(() => {
  cleanup();
});

describe("SettingsToggles", () => {
  it("shows a loading state instead of the toggles while preferences are loading", () => {
    render(
      <SettingsToggles
        loading={true}
        alarmEnabled={true}
        notificationsEnabled={false}
        notificationPermission="default"
        onToggleAlarm={vi.fn()}
        onToggleNotifications={vi.fn()}
      />,
    );

    expect(screen.queryByLabelText("Alarm")).toBeNull();
    expect(screen.getByText("Cargando preferencias…")).toBeTruthy();
  });

  it("reflects the Alarm checkbox state and calls back on toggle", () => {
    const onToggleAlarm = vi.fn();
    render(
      <SettingsToggles
        loading={false}
        alarmEnabled={true}
        notificationsEnabled={false}
        notificationPermission="default"
        onToggleAlarm={onToggleAlarm}
        onToggleNotifications={vi.fn()}
      />,
    );

    const alarmCheckbox = screen.getByLabelText("Alarm") as HTMLInputElement;
    expect(alarmCheckbox.checked).toBe(true);

    fireEvent.click(alarmCheckbox);

    expect(onToggleAlarm).toHaveBeenCalledWith(false);
  });

  it("calls back with true when enabling notifications", () => {
    const onToggleNotifications = vi.fn();
    render(
      <SettingsToggles
        loading={false}
        alarmEnabled={true}
        notificationsEnabled={false}
        notificationPermission="default"
        onToggleAlarm={vi.fn()}
        onToggleNotifications={onToggleNotifications}
      />,
    );

    fireEvent.click(screen.getByLabelText("Notificaciones"));

    expect(onToggleNotifications).toHaveBeenCalledWith(true);
  });

  it("shows the blocked-by-browser state without disabling the ability to turn notifications off", () => {
    render(
      <SettingsToggles
        loading={false}
        alarmEnabled={true}
        notificationsEnabled={false}
        notificationPermission="denied"
        onToggleAlarm={vi.fn()}
        onToggleNotifications={vi.fn()}
      />,
    );

    expect(screen.getByText("(bloqueadas por el navegador)")).toBeTruthy();
    const checkbox = screen.getByLabelText(
      "Notificaciones",
    ) as HTMLInputElement;
    expect(checkbox.disabled).toBe(true);
  });
});
