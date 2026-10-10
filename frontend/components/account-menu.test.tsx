import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "@/lib/api/schema";
import { AccountMenu } from "./account-menu";

type SettingsResponseBody = components["schemas"]["SettingsResponse"];
type UserEvent = ReturnType<typeof userEvent.setup>;

const getMock = vi.fn();
const postMock = vi.fn();
const patchMock = vi.fn();
const deleteMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
    POST: (...args: unknown[]) => postMock(...args),
    PATCH: (...args: unknown[]) => patchMock(...args),
    DELETE: (...args: unknown[]) => deleteMock(...args),
  },
}));

function ok(status = 200): Response {
  return { status } as Response;
}

/** jsdom's `window.location.assign` isn't spy-able directly; replace the whole object instead. */
function mockLocationAssign() {
  const assign = vi.fn();
  Object.defineProperty(window, "location", {
    value: { ...window.location, assign },
    writable: true,
    configurable: true,
  });
  return assign;
}

function makeSettings(overrides: Partial<SettingsResponseBody> = {}): SettingsResponseBody {
  return {
    alarm_enabled: true,
    notifications_enabled: false,
    time_zone: "America/Argentina/Buenos_Aires",
    ...overrides,
  };
}

/** Renders the menu and opens it; most tests then drill into one specific sub-form. */
async function renderAndOpenMenu(user: UserEvent) {
  render(<AccountMenu />);
  await user.click(screen.getByRole("button", { name: "Cuenta" }));
}

async function renderAndOpenSubView(user: UserEvent, subViewButtonName: string) {
  await renderAndOpenMenu(user);
  await user.click(await screen.findByRole("button", { name: subViewButtonName }));
}

beforeEach(() => {
  getMock.mockReset();
  postMock.mockReset();
  patchMock.mockReset();
  deleteMock.mockReset();
  getMock.mockResolvedValue({ data: makeSettings(), error: undefined, response: ok() });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AccountMenu — opening", () => {
  it("shows the four account actions once opened", async () => {
    const user = userEvent.setup();
    await renderAndOpenMenu(user);

    expect(await screen.findByRole("button", { name: "Cambiar contraseña" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cambiar zona horaria" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Borrar cuenta" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument();
  });
});

describe("AccountMenu — change password (Story 9)", () => {
  it("submits current and new password, then shows the session-revocation notice", async () => {
    postMock.mockResolvedValue({ error: undefined, response: ok(204) });
    const user = userEvent.setup();
    await renderAndOpenSubView(user, "Cambiar contraseña");

    await user.type(screen.getByLabelText("Contraseña actual"), "old-pass");
    await user.type(screen.getByLabelText("Contraseña nueva"), "new-pass-123");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith("/api/v1/auth/change-password", {
        body: { current_password: "old-pass", new_password: "new-pass-123" },
      });
    });
    expect(
      await screen.findByText("Contraseña actualizada. Tus otras sesiones se cerraron."),
    ).toBeInTheDocument();
  });

  it("surfaces a wrong-current-password error from the HTTP interface", async () => {
    postMock.mockResolvedValue({
      error: { detail: "email o contraseña incorrectos", code: "invalid_credentials" },
      response: ok(401),
    });
    const user = userEvent.setup();
    await renderAndOpenSubView(user, "Cambiar contraseña");

    await user.type(screen.getByLabelText("Contraseña actual"), "wrong");
    await user.type(screen.getByLabelText("Contraseña nueva"), "new-pass-123");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("email o contraseña incorrectos");
  });
});

describe("AccountMenu — change time zone (Story 5)", () => {
  it("surfaces a settings-load error instead of remaining in the loading state", async () => {
    getMock.mockResolvedValue({
      data: undefined,
      error: { detail: "No se pudo cargar la configuración.", code: "settings_unavailable" },
      response: ok(500),
    });
    const user = userEvent.setup();
    await renderAndOpenSubView(user, "Cambiar zona horaria");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudo cargar la configuración.",
    );
    expect(screen.queryByText("Cargando…")).not.toBeInTheDocument();
  });

  it("loads the current time zone and PATCHes Settings with it replaced, preserving the rest", async () => {
    patchMock.mockResolvedValue({
      data: makeSettings({ time_zone: "Europe/Madrid" }),
      error: undefined,
      response: ok(),
    });
    const user = userEvent.setup();
    await renderAndOpenSubView(user, "Cambiar zona horaria");

    const input = await screen.findByLabelText("Zona horaria");
    expect(input).toHaveValue("America/Argentina/Buenos_Aires");
    await user.clear(input);
    await user.type(input, "Europe/Madrid");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      expect(patchMock).toHaveBeenCalledWith("/api/v1/settings", {
        body: {
          alarm_enabled: true,
          notifications_enabled: false,
          time_zone: "Europe/Madrid",
        },
      });
    });
    expect(await screen.findByText("Zona horaria actualizada.")).toBeInTheDocument();
  });

  it("surfaces an invalid-time-zone error from the HTTP interface", async () => {
    patchMock.mockResolvedValue({
      data: undefined,
      error: { detail: "'Nowhere' is not a valid IANA time zone.", code: "invalid_time_zone" },
      response: ok(422),
    });
    const user = userEvent.setup();
    await renderAndOpenSubView(user, "Cambiar zona horaria");

    const input = await screen.findByLabelText("Zona horaria");
    await user.clear(input);
    await user.type(input, "Nowhere");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "'Nowhere' is not a valid IANA time zone.",
    );
  });
});

describe("AccountMenu — delete account (Story 10)", () => {
  it("confirms with the password, deletes, and redirects to /login", async () => {
    deleteMock.mockResolvedValue({ error: undefined, response: ok(204) });
    const assignSpy = mockLocationAssign();
    const user = userEvent.setup();
    await renderAndOpenSubView(user, "Borrar cuenta");

    await user.type(screen.getByLabelText("Contraseña"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Borrar cuenta" }));

    await waitFor(() => {
      expect(deleteMock).toHaveBeenCalledWith("/api/v1/auth/me", {
        body: { password: "correct-horse" },
      });
    });
    await waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith("/login");
    });
  });

  it("surfaces a wrong-password error without deleting anything observable", async () => {
    deleteMock.mockResolvedValue({
      error: { detail: "email o contraseña incorrectos", code: "invalid_credentials" },
      response: ok(401),
    });
    const user = userEvent.setup();
    await renderAndOpenSubView(user, "Borrar cuenta");

    await user.type(screen.getByLabelText("Contraseña"), "wrong");
    await user.click(screen.getByRole("button", { name: "Borrar cuenta" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("email o contraseña incorrectos");
  });
});

describe("AccountMenu — logout (Story 8)", () => {
  it("logs out and redirects to /login", async () => {
    postMock.mockResolvedValue({ error: undefined, response: ok(204) });
    const assignSpy = mockLocationAssign();
    const user = userEvent.setup();
    await renderAndOpenMenu(user);

    await user.click(await screen.findByRole("button", { name: "Cerrar sesión" }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith("/api/v1/auth/logout");
    });
    await waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith("/login");
    });
  });
});

describe("AccountMenu — 401 mid-session (reuses the shared redirect helper)", () => {
  it("redirects to /login instead of showing a generic error", async () => {
    getMock.mockResolvedValue({ data: undefined, error: undefined, response: ok(401) });
    const assignSpy = mockLocationAssign();
    const user = userEvent.setup();
    await renderAndOpenSubView(user, "Cambiar zona horaria");

    await waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith("/login");
    });
  });
});
