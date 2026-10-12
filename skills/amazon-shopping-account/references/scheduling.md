# Continuation and scheduling

Use this procedure for a requested two-day run or its existing schedule. Initial setup alone does not schedule work.

## Choose and prepare continuation

Prefer an available scheduler that resumes the same agent session. An existing documented agent runner is also usable. Verify that it can access the persistent skill/state files, dedicated browser, credentials, and registration password from its actual execution context. A timer that only opens a page is not an agent runner.

For new schedules use the user's requested time, otherwise **09:00 on the next eligible local day** in the saved timezone. Determine computer/session availability with available tools; ask only for information you cannot establish. If unattended execution is unavailable, use the manual fallback. Do not invent a runner, install a service, or promise wakeup of an unavailable computer.

Read `workflow.py status ACCOUNT_ID`. Reconcile any existing schedule with its provider and reuse it. Before creating a new task, save its intent:

```text
PY SKILL/scripts/workflow.py schedule-prepare ACCOUNT_ID --target-kind session --target-id OBSERVED_SESSION_ID --local-time HH:MM
```

For an existing runner use `--target-kind runner --target-id VERIFIED_RUNNER_ID_OR_PATH`. Identifiers and task instructions contain no secrets.

Create the task through that scheduler's supported interface, preferably as one execution. If recurrence is required, continue only until completion. Include the account and execution target so an uncertain result can be located. After confirmed creation:

```text
PY SKILL/scripts/workflow.py schedule-record ACCOUNT_ID --intent-id SAVED_INTENT_ID --automation-id RETURNED_TASK_ID
```

Confirm the accepted date/time and reconcile it if the actual Day 1 date changes. Eligibility follows the next local calendar date, not a fixed 24-hour delay.

If creation is uncertain, find the existing task rather than creating another. Record `schedule-creation-result ACCOUNT_ID --intent-id ID --outcome uncertain`; use `confirmed_absent` only after establishing absence.

## Resume instruction and manual fallback

Give the scheduled runner this instruction with resolved paths:

> Read ABSOLUTE_SKILL_PATH/SKILL.md and resume ACCOUNT_ID from ABSOLUTE_STATE_PATH on the original computer. Reconcile saved progress with the live browser, then perform only the next requested step after its eligible date. Preserve the profile, allowlist, SMS limits, and existing authorization. If complete, do only pending schedule cleanup. Report only completion, failure, or required user action.

Without a usable scheduler, leave `schedule` empty, save Day 1, and provide this dated resume instruction once. Do not stay running overnight or describe a reminder as automatic execution.

Resume a resolved blocker under the existing full-run authorization. Preserve an explicit user pause or cancellation; if its reason is unknown, clarify before reactivation. Do not repeat authorization requests for an unchanged workflow.

## Pause and cleanup

If unattended execution is blocked, pause its task when supported and record the result; an already-ended one-time task may need no pause. Avoid repeated unchanged notifications.

For pause, resume, or removal, record intent first:

```text
PY SKILL/scripts/workflow.py schedule-action ACCOUNT_ID --automation-id SAVED_TASK_ID --action remove
```

Perform the action on that exact task through its scheduler, then record confirmed success or uncertainty:

```text
PY SKILL/scripts/workflow.py schedule-result ACCOUNT_ID --automation-id SAVED_TASK_ID --action remove --outcome confirmed
```

Use `pause` / `resume` as applicable, or `--outcome uncertain` after an ambiguous result. Inspect the scheduler before retrying.

After completion remove the saved schedule, preserving account state, profile, inbox, and credentials. A failed cleanup leaves the account complete and cleanup pending; retry only cleanup. A lost creation result still needs reconciliation even without a saved task ID.
