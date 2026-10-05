import { LogoutButton } from "@/src/auth/logout-button";
import { TimerPanel } from "@/src/timer/TimerPanel";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center gap-4 py-8">
      <h1 className="font-olivetta text-accent text-3xl font-semibold">
        Pomodoro Collective
      </h1>
      <TimerPanel />
      <LogoutButton />
    </main>
  );
}
