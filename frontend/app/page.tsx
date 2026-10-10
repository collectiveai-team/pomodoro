import { TimerPanel } from "@/components/timer-panel";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-6">
      <TimerPanel />
      <p className="text-sm text-gray-500">The Tasks and History panels are on their way.</p>
    </main>
  );
}
