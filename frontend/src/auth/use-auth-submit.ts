import { useRouter } from "next/navigation";
import { useState } from "react";
import type { AuthResult } from "./client";

export function useAuthSubmit() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(action: () => Promise<AuthResult>) {
    setSubmitting(true);
    setError(null);

    const result = await action();

    if (!result.ok) {
      setError(result.message);
      setSubmitting(false);
      return;
    }

    router.push("/");
  }

  return { error, submitting, submit };
}
