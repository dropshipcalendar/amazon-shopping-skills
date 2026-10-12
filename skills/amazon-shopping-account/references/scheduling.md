# Scheduling both days

Follow the default and overrides in [SKILL.md](../SKILL.md). An install-and-use request includes both days; explicit setup-only or no-scheduling requests create no tasks.

## Verify the runner

Prefer a scheduler that resumes the same agent session; an existing documented agent runner is also usable. Verify access to the persistent skill/state files, dedicated browser, credentials, and secure registration-password entry from the actual execution context. A timer that only opens a page is insufficient. Do not invent a runner, install a service, or promise wakeup of an unavailable computer.

Use `workflow.py status ACCOUNT_ID` before every scheduling action. Reconcile the saved task with its scheduler; never create duplicates or revive a user pause/cancellation. Existing records without a `step` are legacy Day 2 tasks: preserve and inspect them rather than replacing them with Day 1 tasks.

## Prepare and confirm Day 1

After setup succeeds, reserve Day 1's intent. This helper only saves local state; it does not create a live task:

```text
PY SKILL/scripts/workflow.py schedule-prepare ACCOUNT_ID --step day-one --target-kind session --target-id OBSERVED_SESSION_ID
```

The default `first_run_at` is five minutes from now and stays fixed on retries. For an existing runner use `--target-kind runner --target-id VERIFIED_RUNNER_ID_OR_PATH`. For an explicit user-selected date/time, add `--run-at ISO_TIME_WITH_OFFSET`; for the next occurrence of a local clock time, use `--local-time HH:MM` instead. Use the saved timezone. Identifiers and task prompts contain no secrets.

Create a one-time task through the scheduler's supported interface, using the exact returned `first_run_at`. If only recurrence is supported, remove the task after its step finishes. Include the account ID, saved intent ID, and step in the task so an uncertain result can be found. Inspect the created task to verify its target and accepted execution time, then record both:

```text
PY SKILL/scripts/workflow.py schedule-record ACCOUNT_ID --intent-id SAVED_INTENT_ID --automation-id RETURNED_TASK_ID --run-at VERIFIED_EXECUTION_TIME
```

The accepted time must match the saved intent. If it differs, `schedule-record` saves its ID and returns `timing_mismatch`. Correct that same task's time and record its verified result again; do not create a replacement or call it ready. Only then report Day 1 as scheduled using the short setup-and-timeline response in SKILL.md. Day 2 is planned, not yet scheduled.

If creation is uncertain, locate the existing task before retrying. Record `schedule-creation-result ACCOUNT_ID --intent-id ID --outcome uncertain`; use `confirmed_absent` only after verifying no task exists. An unchanged pending intent is not permission to repeat a creation request blindly.

## Transition to Day 2

Finish Day 1 with `browse-stop --result completed`. This records the actual completion time, computes the following local calendar date, and requests Day 1 task cleanup. Interrupted browsing does not start Day 2's date calculation.

Remove the Day 1 task using the cleanup procedure below. If a one-time task expired automatically, verify it can no longer run before recording removal. Resolve a lost creation result as removed or confirmed absent. Do not proceed with an unresolved Day 1 task.

Then prepare Day 2 using the same verified execution target:

```text
PY SKILL/scripts/workflow.py schedule-prepare ACCOUNT_ID --step day-two --target-kind session --target-id OBSERVED_SESSION_ID
```

The default is 09:00 on the local day after actual Day 1 completion. A delayed handoff uses today at 09:00 if still future, otherwise five minutes from now. User-selected `--local-time` or `--run-at` overrides must respect Day 2's eligible date. A nonexistent daylight-saving clock time needs a valid replacement. A repeated clock time uses its first occurrence.

Create, inspect, and record this task as above, then report its confirmed date/time. The helper preserves the removed Day 1 task in `schedule_history` before creating the Day 2 intent. Never repeat Day 1 to repair Day 2 scheduling.

## Scheduled prompt and manual fallback

Give each task this instruction with resolved paths, account, step, and intent ID:

> Read ABSOLUTE_SKILL_PATH/SKILL.md and resume ACCOUNT_ID from ABSOLUTE_STATE_PATH on the original computer for STEP and INTENT_ID. Reconcile saved progress with the live browser and scheduler. If this is an obsolete task, do no account work; clean up only that obsolete task. Run only the due step, retaining the profile, allowlist, spending limits, and authorization. After Day 1, remove its task and arrange Day 2 using the actual completion date. After registration, remove the remaining task. Report only milestones, failure, or required user action.

Without a usable scheduler, do not report automatic execution. Say that nothing is scheduled and give the next manual instruction. If the full workflow is authorized, Day 1 may run now as the fallback; after it finishes, provide Day 2's eligible date and a resume instruction. Do not remain running overnight or describe a reminder as execution.

Resume resolved blockers under existing full-run authorization. Preserve explicit pauses and cancellations. If their reason is unknown, clarify before reactivation. Avoid repeated unchanged notifications.

## Cleanup and pause

Record intent before acting on the exact saved task:

```text
PY SKILL/scripts/workflow.py schedule-action ACCOUNT_ID --automation-id SAVED_TASK_ID --action remove
```

Remove it through the scheduler, verify removal, then record:

```text
PY SKILL/scripts/workflow.py schedule-result ACCOUNT_ID --automation-id SAVED_TASK_ID --action remove --outcome confirmed
```

Use `pause` / `resume` where appropriate, or `--outcome uncertain` after an ambiguous result. Inspect before retrying. A finished step permits removal only. An unfinished step with a blocker may pause when supported.

After registration remove the remaining task and preserve account state, profile, inbox, credentials, and task history. A failed cleanup leaves the step finished with cleanup pending; retry cleanup only, not browsing or signup. A lost creation result still requires reconciliation even without a saved task ID.
