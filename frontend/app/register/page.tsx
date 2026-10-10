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
        title="Register"
        submitLabel="Create account"
        onSubmit={handleSubmit}
        footer={
          <p className="text-sm">
            Already have an account?{" "}
            <Link href="/login" className="underline">
              Log in
            </Link>
          </p>
        }
      />
    </main>
  );
}
