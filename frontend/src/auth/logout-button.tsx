"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { logoutUser } from "./client";

export function LogoutButton() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setPending(true);
    setError(null);

    const result = await logoutUser();

    if (!result.ok) {
      setPending(false);
      setError("No se pudo cerrar la sesión. Intentá de nuevo.");
      return;
    }

    router.replace("/login");
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={handleClick}
        disabled={pending}
        className="rounded-md border border-accent px-4 py-2 text-sm font-semibold text-accent disabled:opacity-60"
      >
        Cerrar sesión
      </button>

      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}
