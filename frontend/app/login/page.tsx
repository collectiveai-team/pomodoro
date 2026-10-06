"use client";

import { type FormEvent, useState } from "react";
import { AuthForm } from "@/src/auth/auth-form";
import { loginUser } from "@/src/auth/client";
import { useAuthSubmit } from "@/src/auth/use-auth-submit";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { error, submitting, submit } = useAuthSubmit();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit(() => loginUser({ email, password }));
  }

  return (
    <AuthForm
      title="Iniciar sesión"
      submitLabel="Iniciar sesión"
      email={email}
      onEmailChange={setEmail}
      password={password}
      onPasswordChange={setPassword}
      passwordAutoComplete="current-password"
      error={error}
      submitting={submitting}
      onSubmit={handleSubmit}
      footerText="¿No tenés cuenta?"
      footerLinkHref="/register"
      footerLinkText="Registrate"
    />
  );
}
