"use client";

import { type FormEvent, useEffect, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { toApiError } from "@/lib/api-error";
import { redirectToLoginOn401 } from "@/lib/http-session";

type SettingsResponseBody = components["schemas"]["SettingsResponse"];

type MenuView = "closed" | "menu" | "password" | "timezone" | "delete";

/** All IANA time zones the browser knows, for the time-zone field's typeahead (Story 5). */
const TIME_ZONES: string[] =
  typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [];

/**
 * A wrong password for change-password/delete-account is also a 401 (`InvalidCredentialsError`,
 * same status the expired-session guard uses) but carries the domain error's own `code`, so it's
 * shown inline here instead of being mistaken for a session-expiry redirect.
 */
const WRONG_PASSWORD_CODE = "invalid_credentials";

/** Redirects via the shared 401 helper unless this 401 is really just a wrong password. */
async function redirectUnlessWrongPassword(response: Response, code: string): Promise<boolean> {
  if (code === WRONG_PASSWORD_CODE) {
    return false;
  }
  return redirectToLoginOn401(response);
}

interface SubFormProps {
  onCancel: () => void;
  onError: (message: string) => void;
}

interface FormActionsProps {
  submitLabel: string;
  submitting: boolean;
  onCancel: () => void;
}

/** The submit/cancel button pair every account sub-form ends with. */
function FormActions({ submitLabel, submitting, onCancel }: FormActionsProps) {
  return (
    <div className="flex gap-2">
      <button type="submit" disabled={submitting} className="btn-primary">
        {submitLabel}
      </button>
      <button type="button" onClick={onCancel} className="btn-secondary">
        Cancelar
      </button>
    </div>
  );
}

/** Change-password form: current + new password, then every other session is revoked (Story 9). */
function ChangePasswordForm({
  onCancel,
  onError,
  onDone,
}: SubFormProps & { onDone: (notice: string) => void }) {
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setSubmitting(true);
    const { error, response } = await apiClient.POST("/api/v1/auth/change-password", {
      body: {
        current_password: String(data.get("current_password") ?? ""),
        new_password: String(data.get("new_password") ?? ""),
      },
    });
    setSubmitting(false);
    if (error === undefined) {
      form.reset();
      onDone("Contraseña actualizada. Tus otras sesiones se cerraron.");
      return;
    }
    const apiError = toApiError(error);
    if (await redirectUnlessWrongPassword(response, apiError.code)) {
      return;
    }
    onError(apiError.message);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <label className="flex flex-col gap-1 text-sm" htmlFor="current_password">
        Contraseña actual
        <input
          id="current_password"
          name="current_password"
          type="password"
          autoComplete="current-password"
          required
          className="field-input"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm" htmlFor="new_password">
        Contraseña nueva
        <input
          id="new_password"
          name="new_password"
          type="password"
          autoComplete="new-password"
          required
          className="field-input"
        />
      </label>
      <FormActions submitLabel="Guardar" submitting={submitting} onCancel={onCancel} />
    </form>
  );
}

/** Change-time-zone form: a full-replace Settings PATCH keeping Alarm/notifications (Story 5). */
function TimeZoneForm({
  settings,
  onCancel,
  onError,
  onDone,
}: SubFormProps & {
  settings: SettingsResponseBody;
  onDone: (settings: SettingsResponseBody) => void;
}) {
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const timeZone = String(data.get("time_zone") ?? "");
    setSubmitting(true);
    const {
      data: updated,
      error,
      response,
    } = await apiClient.PATCH("/api/v1/settings", {
      body: { ...settings, time_zone: timeZone },
    });
    setSubmitting(false);
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (error !== undefined || !updated) {
      onError(toApiError(error).message);
      return;
    }
    onDone(updated);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <label className="flex flex-col gap-1 text-sm" htmlFor="time_zone">
        Zona horaria
        <input
          id="time_zone"
          name="time_zone"
          list="time-zone-options"
          defaultValue={settings.time_zone}
          required
          className="field-input"
        />
        <datalist id="time-zone-options">
          {TIME_ZONES.map((zone) => (
            <option key={zone} value={zone} />
          ))}
        </datalist>
      </label>
      <FormActions submitLabel="Guardar" submitting={submitting} onCancel={onCancel} />
    </form>
  );
}

/** Delete-account form: the current password confirms permanent deletion (Story 10). */
function DeleteAccountForm({ onCancel, onError }: SubFormProps) {
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setSubmitting(true);
    const { error, response } = await apiClient.DELETE("/api/v1/auth/me", {
      body: { password: String(data.get("password") ?? "") },
    });
    if (error === undefined) {
      window.location.assign("/login");
      return;
    }
    const apiError = toApiError(error);
    setSubmitting(false);
    if (await redirectUnlessWrongPassword(response, apiError.code)) {
      return;
    }
    onError(apiError.message);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <p className="text-sm">Esto borra tu cuenta y todos tus datos. No se puede deshacer.</p>
      <label className="flex flex-col gap-1 text-sm" htmlFor="delete_password">
        Contraseña
        <input
          id="delete_password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className="field-input"
        />
      </label>
      <FormActions submitLabel="Borrar cuenta" submitting={submitting} onCancel={onCancel} />
    </form>
  );
}

/** The account menu: change password, change time zone, delete account, logout (Stories 8-10). */
export function AccountMenu() {
  const [view, setView] = useState<MenuView>("closed");
  const [settings, setSettings] = useState<SettingsResponseBody | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  // Fetched lazily, only once, when the time-zone form is actually opened.
  useEffect(() => {
    if (view !== "timezone" || settings !== null) {
      return;
    }
    let cancelled = false;
    async function load() {
      const { data, error: loadError, response } = await apiClient.GET("/api/v1/settings");
      if (await redirectToLoginOn401(response)) {
        return;
      }
      if (cancelled) {
        return;
      }
      if (loadError !== undefined || !data) {
        setError(toApiError(loadError).message);
        return;
      }
      setSettings(data);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [view, settings]);

  function openMenu() {
    setError(null);
    setNotice(null);
    setView("menu");
  }

  function closeMenu() {
    setView("closed");
    setError(null);
    setNotice(null);
  }

  async function handleLogout() {
    setLoggingOut(true);
    const { error: logoutError, response } = await apiClient.POST("/api/v1/auth/logout");
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (logoutError !== undefined) {
      setLoggingOut(false);
      setError(toApiError(logoutError).message);
      return;
    }
    window.location.assign("/login");
  }

  if (view === "closed") {
    return (
      <button type="button" onClick={openMenu} className="btn-secondary" aria-haspopup="true">
        Cuenta
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-ink/15 bg-base p-4">
      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}
      {notice ? <p className="text-sm">{notice}</p> : null}

      {view === "menu" ? (
        <>
          <button type="button" onClick={() => setView("password")} className="btn-secondary">
            Cambiar contraseña
          </button>
          <button type="button" onClick={() => setView("timezone")} className="btn-secondary">
            Cambiar zona horaria
          </button>
          <button type="button" onClick={() => setView("delete")} className="btn-secondary">
            Borrar cuenta
          </button>
          <button
            type="button"
            disabled={loggingOut}
            onClick={handleLogout}
            className="btn-primary"
          >
            Cerrar sesión
          </button>
          <button type="button" onClick={closeMenu} className="btn-secondary">
            Cerrar
          </button>
        </>
      ) : null}

      {view === "password" ? (
        <ChangePasswordForm
          onCancel={() => setView("menu")}
          onError={setError}
          onDone={(message) => {
            setNotice(message);
            setView("menu");
          }}
        />
      ) : null}

      {view === "timezone" ? (
        settings ? (
          <TimeZoneForm
            settings={settings}
            onCancel={() => setView("menu")}
            onError={setError}
            onDone={(updated) => {
              setSettings(updated);
              setNotice("Zona horaria actualizada.");
              setView("menu");
            }}
          />
        ) : error ? null : (
          <p>Cargando…</p>
        )
      ) : null}

      {view === "delete" ? (
        <DeleteAccountForm onCancel={() => setView("menu")} onError={setError} />
      ) : null}
    </div>
  );
}
