# A Pomodoro can start from ReadyForNext on any Active Task

Extends the Timer state machine in the spec and ADR-0003. After a Pomodoro completes the Timer is `ReadyForNext`, previously offering only "start the Break" or "next Pomodoro on the same Task". A User who finishes a Pomodoro and wants to skip the Break and work on a different Task would have had to start the Break and skip it.

`start` now accepts `Idle` **or** `ReadyForNext`: it creates a new Timer running a Pomodoro on the given Task, with no Break. The Break cadence is unaffected because it is derived from the count of completed Pomodoros, which skipping a Break does not change.

A running or paused Pomodoro stays tied to its Task (US56): `start` from `PomodoroRunning`, `PomodoroPaused`, `AskingToLog`, `BreakRunning` or `BreakPaused` still fails with 409 and the current Timer.

At the API, `POST /timer/start` accepts `expected_phase` of `Idle` or `ReadyForNext`, still rejects a stale phase with 409 and the current snapshot, and requires the Task to be one of the caller's Active Tasks (404 `task_not_found` otherwise).

## Considered Options

- **Require starting and skipping the Break first**: two round trips and a spurious Break for a transition the User means as one action.
- **A separate "start on another Task" endpoint**: duplicates `start`'s phase guard and Task checks for no behavioural difference.
