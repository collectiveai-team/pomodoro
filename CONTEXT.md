# Pomodoro Collective

A Linux/Mac desktop app that times the Pomodoro technique and tracks how much of it went to each task.

## Language

**Task** (tarea):
A unit of work with a single free-text description (no separate name/description fields) that Pomodoros can be dedicated to. A Task is either **active** or **archived**, and is editable (its text and Tags) at any time.
_Avoid_: item, todo, entry

**Active Task**:
A Task shown in the selectable list a Pomodoro can currently be dedicated to. Its text must be unique among Active Tasks (compared case- and whitespace-insensitively). Active Tasks have a manual display order; a newly created Task is placed first.
_Avoid_: assignable task, current task

**Archived Task**:
A Task retired from the active list into a separate list, keeping its accumulated Pomodoro/time history. The archived list is shown most-recently-archived first. An Archived Task can be **unarchived** back to the active list (placed last), unless its text would then collide with an existing Active Task's.
_Avoid_: deleted task, completed task

**Delete** (Task):
Permanent removal of a Task, distinct from archiving. Only possible for a Task with no dedicated Pomodoro at all — complete or partial — ever recorded against it; once any Pomodoro time has been dedicated, archiving is the only way to retire it.
_Avoid_: remove, discard (as synonyms when archiving is meant instead)

**Pomodoro**:
A single 25-minute focus interval dedicated to one Task, from start to stop or completion. It can be paused and resumed without penalty. A Pomodoro that reaches 25 minutes is *completed*; one stopped early is *interrupted*, and the user chooses whether to log its elapsed time or discard it.
_Avoid_: cycle, work interval, focus session, session

**Break**:
The rest interval that follows a Pomodoro: 5 minutes, or 10 minutes every 5th completed Pomodoro. Skippable, and can be paused and resumed like a Pomodoro. Break time is never added to any Task's dedicated time.
_Avoid_: descanso, rest, pause

**Alarm**:
The audible cue played when a Pomodoro or a Break ends on its own; the user can turn it on or off. Skipping a Break does not play the Alarm.
_Avoid_: notification sound, chime

**Tag**:
A user-defined label attached to a Task, used to group and filter Tasks. A Tag has its own identity shared across every Task that carries it — matching is case-insensitive and trims whitespace, so renaming a Tag renames it everywhere it's used, and a Task is free to carry zero Tags.
_Avoid_: category, label (as a synonym for Tag itself, use Tag)

**History**:
The day-by-day record of the dedicated time each Task received, viewable by month like a calendar. It includes time from both completed and logged-interrupted Pomodoros.
_Avoid_: log, calendar (calendar is the view; History is the record it shows)
