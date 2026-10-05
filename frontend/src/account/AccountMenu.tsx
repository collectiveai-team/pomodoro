"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { logoutUser } from "@/src/auth/client";
import {
  changePassword,
  deleteAccount,
  fetchSettings,
  updateTimeZone,
} from "./client";

/**
 * Account menu: change password, time zone (T14's Settings API), delete
 * account (password-confirmed), and logout (stories 5, 8, 9, 10). Logout
 * reuses T20's `logoutUser` wrapper rather than re-implementing the
 * csrf_guard-aware body-less POST.
 */

function supportedTimeZones(current: string): string[] {
  try {
    const zones = Intl.supportedValuesOf("timeZone");
    return zones.includes(current) ? zones : [current, ...zones];
  } catch {
    return [current];
  }
}

export function AccountMenu() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const [timeZone, setTimeZone] = useState<string | null>(null);
  const [timeZoneOptions, setTimeZoneOptions] = useState<string[]>([]);
  const [timeZoneError, setTimeZoneError] = useState<string | null>(null);
  const [timeZoneSaving, setTimeZoneSaving] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [logoutPending, setLogoutPending] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || timeZone !== null) {
      return;
    }
    let cancelled = false;
    void fetchSettings().then((result) => {
      if (cancelled) {
        return;
      }
      if (result.ok) {
        setTimeZone(result.settings.time_zone);
        setTimeZoneOptions(supportedTimeZones(result.settings.time_zone));
      } else {
        setTimeZoneError(result.message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [open, timeZone]);

  async function handleTimeZoneChange(nextZone: string): Promise<void> {
    const previous = timeZone;
    setTimeZone(nextZone);
    setTimeZoneSaving(true);
    setTimeZoneError(null);
    const result = await updateTimeZone(nextZone);
    setTimeZoneSaving(false);
    if (result.ok) {
      setTimeZone(result.settings.time_zone);
    } else {
      setTimeZone(previous);
      setTimeZoneError(result.message);
    }
  }

  async function handleChangePassword(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    setPasswordSubmitting(true);
    setPasswordError(null);
    setPasswordSuccess(false);
    const result = await changePassword(currentPassword, newPassword);
    setPasswordSubmitting(false);
    if (result.ok) {
      setCurrentPassword("");
      setNewPassword("");
      setPasswordSuccess(true);
      return;
    }
    setPasswordError(result.message);
  }

  async function handleDeleteAccount(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    setDeleteSubmitting(true);
    setDeleteError(null);
    const result = await deleteAccount(deletePassword);
    setDeleteSubmitting(false);
    if (result.ok) {
      router.replace("/login");
      return;
    }
    setDeleteError(result.message);
  }

  async function handleLogout(): Promise<void> {
    setLogoutPending(true);
    setLogoutError(null);
    const result = await logoutUser();
    if (!result.ok) {
      setLogoutPending(false);
      setLogoutError("No se pudo cerrar la sesión. Intentá de nuevo.");
      return;
    }
    router.replace("/login");
  }

  return (
    <div className="flex w-full max-w-xl flex-col gap-2">
      <button
        type="button"
        onClick={() => setOpen((previous) => !previous)}
        aria-expanded={open}
        aria-controls="account-menu-panel"
        className="min-h-11 self-end rounded-md border border-ink/20 px-4 py-2 text-sm font-semibold text-ink"
      >
        Cuenta
      </button>

      {open ? (
        <section
          id="account-menu-panel"
          className="flex flex-col gap-6 rounded-md border border-ink/10 p-4"
        >
          <div className="flex flex-col gap-2">
            <h2 className="font-olivetta text-lg font-semibold text-ink">
              Zona horaria
            </h2>
            {timeZone === null ? (
              <p className="text-sm text-ink/60">Cargando…</p>
            ) : (
              <select
                value={timeZone}
                onChange={(event) =>
                  void handleTimeZoneChange(event.target.value)
                }
                disabled={timeZoneSaving}
                aria-label="Zona horaria"
                className="min-h-11 rounded-md border border-ink/20 bg-transparent px-3 py-2 text-sm disabled:opacity-60"
              >
                {timeZoneOptions.map((zone) => (
                  <option key={zone} value={zone}>
                    {zone}
                  </option>
                ))}
              </select>
            )}
            {timeZoneError ? (
              <p role="alert" className="text-sm text-red-600">
                {timeZoneError}
              </p>
            ) : null}
          </div>

          <form
            onSubmit={(event) => void handleChangePassword(event)}
            className="flex flex-col gap-2"
          >
            <h2 className="font-olivetta text-lg font-semibold text-ink">
              Cambiar contraseña
            </h2>
            <label className="flex flex-col gap-1 text-sm">
              Contraseña actual
              <input
                type="password"
                required
                autoComplete="current-password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                className="min-h-11 rounded-md border border-ink/20 bg-transparent px-3 py-2"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Contraseña nueva
              <input
                type="password"
                required
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                className="min-h-11 rounded-md border border-ink/20 bg-transparent px-3 py-2"
              />
            </label>
            {passwordError ? (
              <p role="alert" className="text-sm text-red-600">
                {passwordError}
              </p>
            ) : null}
            {passwordSuccess ? (
              <p className="text-sm text-ink/80">Contraseña actualizada.</p>
            ) : null}
            <button
              type="submit"
              disabled={passwordSubmitting}
              className="min-h-11 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              Guardar contraseña
            </button>
          </form>

          <div className="flex flex-col gap-2">
            <h2 className="font-olivetta text-lg font-semibold text-ink">
              Eliminar cuenta
            </h2>
            {confirmingDelete ? (
              <form
                onSubmit={(event) => void handleDeleteAccount(event)}
                className="flex flex-col gap-2"
              >
                <label className="flex flex-col gap-1 text-sm">
                  Confirmá tu contraseña
                  <input
                    type="password"
                    required
                    autoComplete="current-password"
                    value={deletePassword}
                    onChange={(event) => setDeletePassword(event.target.value)}
                    className="min-h-11 rounded-md border border-ink/20 bg-transparent px-3 py-2"
                  />
                </label>
                {deleteError ? (
                  <p role="alert" className="text-sm text-red-600">
                    {deleteError}
                  </p>
                ) : null}
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={deleteSubmitting}
                    className="min-h-11 rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                  >
                    Eliminar cuenta definitivamente
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setConfirmingDelete(false);
                      setDeletePassword("");
                      setDeleteError(null);
                    }}
                    className="min-h-11 rounded-md border border-ink/20 px-4 py-2 text-sm text-ink"
                  >
                    Cancelar
                  </button>
                </div>
              </form>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmingDelete(true)}
                className="min-h-11 self-start rounded-md border border-red-600 px-4 py-2 text-sm font-semibold text-red-600"
              >
                Eliminar cuenta
              </button>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => void handleLogout()}
              disabled={logoutPending}
              className="min-h-11 self-start rounded-md border border-accent px-4 py-2 text-sm font-semibold text-accent disabled:opacity-60"
            >
              Cerrar sesión
            </button>
            {logoutError ? (
              <p role="alert" className="text-sm text-red-600">
                {logoutError}
              </p>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
