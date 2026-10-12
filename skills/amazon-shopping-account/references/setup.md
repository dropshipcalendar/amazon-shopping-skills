# Initial setup and subsequent runs

Use this mode when the user asks to install **and set up**, explicitly requests setup, or authorizes the full workflow. Downloading or installing files alone runs nothing. Authoring, inspection, and tests never authorize live setup. Setup may create one AgentMail organization/inbox; it does not register on Amazon, allocate SMS numbers, purchase credits, browse products, or schedule work.

Keep the first response terse: "I'll prepare the browser and connect email and SMS access. I'll ask you to step in only if a login is needed." On later runs, proceed quietly when checks pass. Ask only for a missing login, funding, spending authorization, or capability; do not repeat generic setup instructions.

1. Follow `platform.md`; run `setup_access.py prepare shopping-01` to initialize/reuse state with the detected local timezone, then configure/verify the dedicated Chrome profile through `browser-profile.md` and `browser-interaction.md`. Use a known user-selected marketplace/timezone override when supplied. Keep provider administration in an existing authorized provider session when available. No new settings page or credential-entry UI is required.
2. Read `credentials.md`. Run `setup_access.py migrate-credentials ACCOUNT_ID` to reuse this account's keys from an earlier installation, then `setup_access.py status ACCOUNT_ID` to discover saved/injected provider access without printing values. If the vault is unavailable, resolve it before provisioning. An existing provider account or assigned inbox must be reconnected, never silently replaced.
3. Connect email with `setup_access.py email-connect ACCOUNT_ID`. If this is genuinely first-time onboarding with no existing AgentMail account to reuse, run the same command with `--allow-signup` under the user's setup authorization. The helper signs up without a human email, securely stores the returned key and inbox, then checks access. This produces a receive-only inbox; do not claim it can send mail or is already claimed by a human. No human-email verification is needed for this receive-only path. Do not auto-retry uncertain signup or rotate a lost key. Existing valid access creates/reuses the workflow's assigned inbox without another provider signup.
4. If SMS is enabled and TextVerified access is absent, reuse its authenticated session or guide login with the single sentence in `credentials.md`. Capture and persist its matching key/email privately. If it has no account, report that prerequisite once; do not create one automatically. Preserve an existing `sms_enabled: false`; skip TextVerified setup and checks for that saved opt-out, and report SMS unavailable if Amazon later requires it.
5. Run the checks below. Select the exact Amazon shopping SMS service from the live list, not another Amazon product or a guessed identifier. Preserve the chosen service in the returned check record. Missing/ambiguous service selection is a blocker, not permission to choose an unrelated service.

```text
PY SKILL/scripts/setup_access.py status ACCOUNT_ID
PY SKILL/scripts/setup_access.py migrate-credentials ACCOUNT_ID
PY SKILL/scripts/setup_access.py email-connect ACCOUNT_ID
PY SKILL/scripts/providers.py phone-services ACCOUNT_ID
PY SKILL/scripts/providers.py phone-check ACCOUNT_ID --service EXACT_RETURNED_SERVICE_NAME
```

6. When SMS is enabled, `phone-check` uses the live one-time quote and balance. Required balance is `max(sms_min_balance_usd, current quote)`; the default minimum is $0.75, not a guaranteed Amazon price. It independently checks the approved cumulative spending cap and allocation limit. If `balance_ok` is false, say: "TextVerified needs at least $X; its balance is $Y. Please add funds in the open tab." Do not top up automatically or promise the deposit minimum equals the shortfall. If `budget_ok` is false, request only the missing spending authorization; balance never grants spending permission. Report setup ready only when enabled connections and required checks pass; with SMS opted out, say email is connected and SMS is disabled.
7. Verify a fresh process can read credentials; for unattended operation also verify the actual runner's vault/injection access. On successful setup say only: "Setup complete. Email and SMS access are connected, and the dedicated browser is ready." If only setup was requested, stop. A full-run request can continue to Day 1 and authorized scheduling.

## Subsequent runs

Read saved progress first. Completed workflows perform only pending schedule cleanup. For unfinished work, reuse saved access and the assigned inbox; never repeat provisioning because a new chat started. Check credentials and balance during setup and again immediately before Day 2 registration. Only purchase an SMS number when the live Amazon form requests it; `phone-create` refreshes the quote and balance again before purchase. Preserve spending and attempt counters.

`setup_access.py status` reports presence and historical checks, not live authentication. `email-connect` validates the assigned inbox; `phone-check` validates SMS access, quote and balance. If either fails, preserve credentials and classify the problem before requesting action. Retry only reads after transient errors. Login prompts are reserved for missing/rejected authentication, not expired SDK tokens or network failures.

## Interrupted setup

Setup stores nonsecret checks under the account's `setup` field. A shared `.connections/agentmail-signup.json` beside the account folders records the one-shot signup intent. A matching vault entry recovers the assigned inbox after a crash. An unresolved intent without its key blocks further signup even if `--allow-signup` is supplied; inspect the existing account/result instead. A different workflow cannot reuse a bootstrap inbox. Do not delete these records to force another signup.

Source: https://docs.agentmail.to/agent-onboarding
