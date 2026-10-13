"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { registerAccount } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();

  async function handleSubmit(email: string, password: string) {
    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    await registerAccount(email, password, timeZone);
    router.push("/");
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <AuthForm
        title="Crear cuenta"
        submitLabel="Crear cuenta"
        onSubmit={handleSubmit}
        footer={
          <p className="text-sm">
            ¿Ya tienes cuenta?{" "}
            <Link href="/login" className="underline">
              Inicia sesión
            </Link>
          </p>
        }
      />
    </main>
  );
}
