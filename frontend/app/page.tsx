import { LogoutButton } from "@/src/auth/logout-button";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="font-olivetta text-accent text-3xl font-semibold">
        Pomodoro Collective
      </h1>
      <LogoutButton />
    </main>
  );
}
