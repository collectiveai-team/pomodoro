"use client";

import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import { fetchCurrentUser } from "./client";
import { PUBLIC_PATHS, requireSession } from "./require-session";

/**
 * Gates every non-public route on a valid session: checks GET /api/auth/me
 * client-side and redirects to /login on a 401 (ADR-0001's same-origin,
 * no-middleware architecture; /login and /register themselves are skipped).
 */
export function SessionGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(() => PUBLIC_PATHS.has(pathname));

  useEffect(() => {
    let cancelled = false;

    requireSession({
      pathname,
      checkSession: fetchCurrentUser,
      redirectToLogin: () => router.replace("/login"),
    }).then((outcome) => {
      if (!cancelled) {
        setReady(outcome !== "redirected");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  if (!ready) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-ink/60">Cargando…</p>
      </main>
    );
  }

  return <>{children}</>;
}
