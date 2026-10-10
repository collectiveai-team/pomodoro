"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthForm } from "@/components/auth-form";
import { login } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();

  async function handleSubmit(email: string, password: string) {
    await login(email, password);
    router.push("/");
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <AuthForm
        title="Log in"
        submitLabel="Log in"
        onSubmit={handleSubmit}
        footer={
          <p className="text-sm">
            No account yet?{" "}
            <Link href="/register" className="underline">
              Register
            </Link>
          </p>
        }
      />
    </main>
  );
}
