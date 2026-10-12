# Continuation and scheduling

The saved account state is the source of progress across days, not conversation memory. A computer-using agent can resume by reading this skill and that state from disk. Scheduling is optional and depends on capabilities actually available to the agent.

Use this flow only while executing a user-authorized two-day run or managing its existing schedule. Editing, downloading, installing, or testing the skill does not authorize a live schedule.

## Choose a continuation method

1. Inspect the current computer and available scheduling capabilities. For a cloud computer, confirm that account data, the browser profile, and the runner survive restarts and remain accessible on Day 2; use a verified persistent volume when needed. A schedule does not make temporary storage persistent. Do not switch to a connected laptop solely because the cloud computer runs Linux. Prefer resuming the existing agent session when supported. An OS task scheduler or another scheduler is also usable if it can invoke an existing, documented agent runner on this computer with a saved task instruction. Do not invent an agent executable, command, API, session ID, or service.
2. Verify that the continuation can read the same skill and state files, access the dedicated browser profile, and obtain credentials and the registration password securely. Run setup checks through that actual runner: the same unlocked OS vault/DBus session or approved secret injection must be accessible, not merely the interactive browser session. A timer that merely opens a page or runs `workflow.py` cannot execute the agent's browser workflow. A reminder is a manual handoff, not unattended execution.
3. If these capabilities are absent, use the manual fallback below. If the user specifically requires unattended completion, explain the missing capability before starting. Do not install a service or provision another agent automatically.
4. Obtain the user's Day 2 local time and use the account's timezone. The next calendar day is not necessarily 24 elapsed hours later. Confirm machine availability and the selected runner's requirements; do not promise that a powered-off computer will wake or a graphical session will be usable while locked.

## Register one supported schedule

Run `workflow.py status ACCOUNT_ID`. If `schedule` exists, reconcile it with the scheduler that owns its task ID before creating anything. Reuse that task; do not silently reactivate paused or removed schedules.

For a new schedule, record an intent before creating the external task:

```text
PY SKILL/scripts/workflow.py schedule-prepare ACCOUNT_ID --target-kind session --target-id OBSERVED_SESSION_ID --local-time HH:MM
```

For a runner, use `--target-kind runner --target-id VERIFIED_RUNNER_ID_OR_PATH`. This is a nonsecret identifier for the verified runner; credentials and secret command arguments do not belong in state. The helper also accepts the older `--thread-id` alias for existing integrations.

Create the task using the selected scheduler's documented interface. Prefer one execution at the intended Day 2 date/time. A daily continuation until completion is acceptable if that scheduler requires recurrence. Supply the resume instruction below to the agent through its actual supported interface, preserving the original profile and account state. Use the scheduler's task description to identify this account, skill, and execution target so an uncertain creation can be reconciled. Never run the browser from two concurrent agent instances.

After confirmed creation, save the actual task ID or unambiguous task path returned by that scheduler:

```text
PY SKILL/scripts/workflow.py schedule-record ACCOUNT_ID --intent-id SAVED_INTENT_ID --automation-id RETURNED_TASK_ID
```

`automation_id` is the helper's generic field for a scheduler task ID. It is not tied to a particular service. Keep enough scheduler information in the identifier or its task description to find the same task later.

If creation is uncertain, inspect that scheduler's task listing and details using the saved account and target identity. Recover and record the existing task. Only verified absence permits `schedule-creation-result --intent-id ID --outcome confirmed_absent` and retrying the same intent. Otherwise record `--outcome uncertain` and report the blocker; do not create a duplicate.

Confirm the schedule before Day 1 when unattended execution was selected. If the actual browsing date changes, reconcile the same task with the new eligibility date. The helper's `first_run_at` is intended timing, not proof that the scheduler accepted it. Ambiguous DST times use the first occurrence; nonexistent local times are rejected.

## Resume instruction

Replace placeholders with actual values. Do not include credentials:

> Read ABSOLUTE_SKILL_PATH/SKILL.md and resume account ACCOUNT_ID from ABSOLUTE_STATE_PATH on the original computer. Inspect saved progress and the live browser before acting. Do not start Day 2 before its saved eligible date. Perform only the next unfinished authorized step, preserving the original profile, product allowlist, one-time SMS mode, spending cap, and attempt limits. If already complete, do only any pending scheduler cleanup. If required input or capability is missing, stop and report the specific action needed. Avoid repeated unchanged notifications; report completion, failure, or required user action.

## Manual fallback

Leave `schedule` empty when none has been created. Complete and save Day 1 normally, then give the user the resume instruction above with the eligible local date and timezone. On or after that date, they can supply it to a computer-using agent with access to the same files and browser profile. Do not manufacture a session/task ID, mark a nonexistent schedule active, or stay running overnight. A reminder may tell the user to invoke the agent, but must not be described as running the workflow automatically.

## Resume, pause, and cleanup

On resumption, read `status`. If complete, clean up only. If too early, take no account action. If Day 1 was interrupted, reconcile its timer and cart; otherwise continue the next eligible phase. Saved files allow resumption even with a fresh conversation or a different compatible agent. They do not grant new purchasing authority or reset counters.

If unattended execution is blocked, disable/pause the exact task using its scheduler, record the confirmed result, and report the specific missing input or capability once. For a one-time task that already ended, inspect its actual status rather than claiming it was paused. Resume or reschedule only after the blocker is resolved and the user authorizes continuation.

For pause, resume, or removal, record intent before changing the scheduler:

```text
PY SKILL/scripts/workflow.py schedule-action ACCOUNT_ID --automation-id SAVED_TASK_ID --action remove
```

Delete that exact task through its scheduler, then confirm deletion or verified absence:

```text
PY SKILL/scripts/workflow.py schedule-result ACCOUNT_ID --automation-id SAVED_TASK_ID --action remove --outcome confirmed
```

Use the same pattern with `pause` or `resume` when the scheduler supports it. Preserve unrelated settings and tasks. Use `--outcome uncertain` after ambiguous results and inspect the scheduler before retrying. Local bookkeeping commands never change an external schedule.

Completion preserves the account's `complete` phase and flags any existing schedule for removal. A failed cleanup never justifies repeating browser work. A lost creation result still needs reconciliation even if no task ID was saved. Manual runs with no schedule have nothing to remove. Never delete the account state, inbox, browser profile, or credentials as scheduler cleanup.
