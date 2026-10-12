# Same-chat continuation

Use this flow only while executing a user-authorized full two-day run or managing its existing schedule. A request to create, edit, inspect, or test the skill does not authorize creating a live automation. An explicit instruction not to schedule takes precedence.

## Preflight and initial scheduling

1. Confirm the current local execution host and actual current chat ID from trusted host context. Never infer an ID from a title. Obtain the user's Day 2 local time if missing; use the account's timezone. Do not choose a hidden time or confuse next calendar day with 24 elapsed hours.
2. Confirm a usable dedicated browser session and unattended access to the required credentials and signup inputs, including a password via an authorized secret manager. The one-run hidden credential prompt cannot supply tomorrow's credentials. Check only presence or read-only authentication, never expose values. Obtain a spending cap for conditional one-time SMS. The machine must be available with the app running; do not promise the scheduler can wake a powered-off computer or guarantee unattended completion of verification.
3. Run `workflow.py status ACCOUNT_ID`. If `schedule` exists, inspect that record and the host scheduler. Reuse the same automation, never create a replacement blindly. A different requested chat/time needs an explicit update to the existing automation and reconciled local metadata. A paused or removed schedule must not be silently reactivated against the user's intent.
4. With no existing schedule, persist a creation intent first:

```text
PY SKILL/scripts/workflow.py schedule-prepare ACCOUNT_ID --thread-id ACTUAL_CHAT_ID --local-time HH:MM
```

5. Use the host's `automation_update` capability to create a **heartbeat targeting this same chat** on this local host, daily at the selected time, beginning at the intended Day 2 date when supported. Do not create a standalone cron task, a new chat, or an OS scheduler workaround. Use the tool's current supported scheduling format, not handwritten automation directives. The first occurrence of an ambiguous DST time is the intended one; a nonexistent local time is rejected by the helper. The saved `first_run_at` is intended timing, not proof of remote scheduling.
6. After confirmed creation, persist the returned ID against the creation intent:

```text
PY SKILL/scripts/workflow.py schedule-record ACCOUNT_ID --intent-id SAVED_INTENT_ID --automation-id RETURNED_ID
```

Never store an invented ID or a pending operation ID as an automation ID. If creation is uncertain or the process crashes before saving the ID, inspect scheduler records on this host using the account ID and exact target chat. In Codex, use the documented `$CODEX_HOME/automations/*/automation.toml` metadata location (`~/.codex/automations` when unset), then the scheduler's view operation for the matching ID. Recover the matching automation and record its ID. If absence is positively confirmed, `schedule-creation-result --intent-id ID --outcome confirmed_absent` permits retrying the same intent. Otherwise use `--outcome uncertain` and stop. Do not create a duplicate as a recovery tactic. Existing records are returned unchanged by repeated `schedule-prepare`.

7. Run Day 1 after the continuation is confirmed. If the actual first browsing date differs from the planned date, reconcile the existing schedule's start with the new eligibility date, without creating another automation. Save Day 1 results, report the intended continuation, and end the invocation.

## Durable scheduled prompt

Replace placeholders with the actual values; include no credentials:

> Use $amazon-shopping-account at ABSOLUTE_SKILL_PATH to resume account ACCOUNT_ID from ABSOLUTE_STATE_PATH in this chat on the original local host. Read the saved state before acting. Do not act before the intended first-run time or Day 2 eligibility. Resume only the next unfinished authorized step. Preserve the original browser profile, product allowlist, one-time SMS mode, spending and attempt limits. If the workflow is complete, remove only its recorded automation and confirm cleanup; do not repeat browser work. Pause the continuation and notify the user once if human input is required. Stay quiet while waiting or when there is no actionable change; report completion, failure, or required user action.

## On every wakeup

Read `status` and verify the automation/account/chat association. If `complete`, do cleanup only. If too early, return quietly. If Day 1 was interrupted, reconcile its timer and cart before resuming; never skip it. If eligible and Day 1 is finished, resume Day 2 in the same profile. An invocation does not grant new purchasing authority or reset counters. Respect the host's run serialization; do not operate the same profile concurrently from another worker.

If missing input or credentials, or unavailable browser access blocks execution, request a pause of this exact automation, confirm the pause, and notify the user once with the specific action needed. Resume it only after user input authorizes continuation. Unchanged waiting states should not produce repeated notifications.

## Pause, resume, and removal

Record the intended action before calling the scheduler:

```text
PY SKILL/scripts/workflow.py schedule-action ACCOUNT_ID --automation-id SAVED_ID --action remove
```

Call `automation_update` with its supported delete operation for **SAVED_ID only**. After confirmed deletion (or a verified already-absent result), record:

```text
PY SKILL/scripts/workflow.py schedule-result ACCOUNT_ID --automation-id SAVED_ID --action remove --outcome confirmed
```

Use the same two-step pattern with `pause` or `resume` and the host's supported update operation. Preserve other automation settings. An ambiguous result uses `--outcome uncertain`; inspect the remote state before retrying. Local bookkeeping commands never modify a live automation.

`signup-complete` preserves the account's `complete` phase and sets schedule removal pending. Only a confirmed remote removal marks `schedule.status=removed`. A lost creation result with no saved automation ID still requires reconciliation; do not declare cleanup complete merely because the local ID is missing. Removal is idempotent. Never delete the chat, browser profile, credentials, or inbox as schedule cleanup.

Source checked 2026-10-12: https://learn.chatgpt.com/docs/automations
