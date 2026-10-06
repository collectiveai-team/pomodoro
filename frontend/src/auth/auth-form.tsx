"use client";

import Link from "next/link";
import type { FormEvent, ReactNode } from "react";

type AuthFormProps = {
  title: string;
  submitLabel: string;
  email: string;
  onEmailChange: (value: string) => void;
  password: string;
  onPasswordChange: (value: string) => void;
  passwordAutoComplete: "current-password" | "new-password";
  passwordMinLength?: number;
  passwordMaxLength?: number;
  error: string | null;
  submitting: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  footerText: string;
  footerLinkHref: string;
  footerLinkText: string;
};

export function AuthForm({
  title,
  submitLabel,
  email,
  onEmailChange,
  password,
  onPasswordChange,
  passwordAutoComplete,
  passwordMinLength,
  passwordMaxLength,
  error,
  submitting,
  onSubmit,
  footerText,
  footerLinkHref,
  footerLinkText,
}: AuthFormProps): ReactNode {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-4">
        <h1 className="font-olivetta text-2xl font-semibold text-accent">
          {title}
        </h1>

        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => onEmailChange(event.target.value)}
            className="rounded-md border border-ink/20 bg-transparent px-3 py-2"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Contraseña
          <input
            type="password"
            required
            minLength={passwordMinLength}
            maxLength={passwordMaxLength}
            autoComplete={passwordAutoComplete}
            value={password}
            onChange={(event) => onPasswordChange(event.target.value)}
            className="rounded-md border border-ink/20 bg-transparent px-3 py-2"
          />
        </label>

        {error ? (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-accent px-4 py-2 font-semibold text-white disabled:opacity-60"
        >
          {submitLabel}
        </button>

        <p className="text-sm">
          {footerText}{" "}
          <Link href={footerLinkHref} className="text-accent underline">
            {footerLinkText}
          </Link>
        </p>
      </form>
    </main>
  );
}
