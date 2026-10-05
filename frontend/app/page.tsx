import { LogoutButton } from "@/src/auth/logout-button";
import { ActiveTab } from "@/src/tasks/ActiveTab";
import { TimerPanel } from "@/src/timer/TimerPanel";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center gap-4 py-8">
      <h1 className="font-olivetta text-accent text-3xl font-semibold">
        Pomodoro Collective
      </h1>
      <TimerPanel />
      <div className="w-full max-w-xl">
        <ActiveTab />
      </div>
      <LogoutButton />
    </main>
  );
}
