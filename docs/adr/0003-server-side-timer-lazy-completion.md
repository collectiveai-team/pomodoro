# The Timer is persisted on the server and completes lazily

On the web, reloading or closing a tab is routine, and a logged-in User expects the same Timer on every tab and device, so each User has exactly one Timer row on the server holding the phase, the Task in progress, the active time accumulated so far and the instant the current run started (null while paused). Clients compute the countdown locally from that data and re-fetch it on focus and after each action; there is no WebSocket/SSE push in v1.

There is no background job either. Whenever the Timer is read or acted on, the server first settles it against the current time: a Pomodoro whose active time reached 25 minutes is recorded as `completed` with `ended_at` set to the exact moment it ran out (not when it was noticed), and the Timer moves to "ready for the next one"; a Break that ran out moves the Timer to idle. The Alarm and the browser notification only fire on an open page. An action that does not match the Timer's current phase (for example a stale tab pressing "stop" after another paused it) is rejected with 409 and the current Timer, and the client refreshes silently.

## Considered Options

- **Timer only in the browser**: a reload loses the Pomodoro.
- **`localStorage`**: survives a reload but not a second device.
- **A scheduler that completes phases at their deadline**: more infrastructure for no visible difference, since lazy settlement yields the same `ended_at`.
