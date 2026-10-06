"use client";

import { type FormEvent, useState } from "react";
import { AuthForm } from "@/src/auth/auth-form";
import { registerUser } from "@/src/auth/client";
import { detectTimeZone } from "@/src/auth/time-zone";
import { useAuthSubmit } from "@/src/auth/use-auth-submit";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { error, submitting, submit } = useAuthSubmit();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit(() =>
      registerUser({ email, password, time_zone: detectTimeZone() }),
    );
  }

  return (
    <AuthForm
      title="Crear cuenta"
      submitLabel="Crear cuenta"
      email={email}
      onEmailChange={setEmail}
      password={password}
      onPasswordChange={setPassword}
      passwordAutoComplete="new-password"
      passwordMinLength={8}
      passwordMaxLength={128}
      error={error}
      submitting={submitting}
      onSubmit={handleSubmit}
      footerText="¿Ya tenés cuenta?"
      footerLinkHref="/login"
      footerLinkText="Iniciá sesión"
    />
  );
}
