# Initial setup

Follow the entry rule and message style in [SKILL.md](../SKILL.md). Initial setup prepares the profile and provider access. For the default install-and-use request, continue to scheduling after these checks; explicit setup-only requests stop here. Setup itself does not browse Amazon, register, buy SMS numbers, or top up credits.

## Runtime

Use Python 3.11 or newer. Run `workflow.py environment` and use its returned paths. Reuse or create the private Python environment and install `scripts/requirements.txt` there, including after a skill update. Keep workflow data outside the skill folder on persistent storage. Resolve routine setup issues using available tools; report only a capability that needs user action. Do not substitute global Python installation or weaken browser protections.

In commands below, resolve `PY` to the private interpreter and `SKILL` to this complete local folder.

## Connect once

1. Run `PY SKILL/scripts/setup_access.py prepare shopping-01`, using the existing account ID or a known preference when supplied. Defaults are in [configuration](configuration.md). Prepare and verify the dedicated [browser profile](browser-profile.md).
2. Read [credential handling](credentials.md). Run `setup_access.py migrate-credentials ACCOUNT_ID`, then `setup_access.py status ACCOUNT_ID`. Reuse configured access; a locked store needs unlocking, not another provider account.
3. Run `setup_access.py email-connect ACCOUNT_ID --allow-signup`. This reuses existing access or creates a first-time AgentMail organization and receive-only inbox, saving both key and assignment. If an existing AgentMail account is known but its access is missing, reconnect it. Do not repeat an uncertain signup or create a replacement for a lost key.
4. If SMS is enabled, reuse saved TextVerified access or follow the private login/capture procedure in `credentials.md` when missing. Do not create a TextVerified account automatically. Run `providers.py phone-services ACCOUNT_ID`, choose the exact returned Amazon shopping service, then `providers.py phone-check ACCOUNT_ID --service EXACT_RETURNED_SERVICE_NAME`. Interpret readiness using [phone](phone.md). Preserve a saved SMS opt-out and skip this branch when disabled.
5. Verify access from a fresh helper process. For an unattended run, also verify access from the actual scheduled runner. A historical ready flag is not a live connection check.

If funding is short, say: "TextVerified needs at least $X; its balance is $Y. Please add funds in the open tab." Ask once for a missing spending cap; balance does not authorize spending. Continue independent preparation while awaiting required input.

When ready for the default full workflow, follow [scheduling](scheduling.md) before ending this turn. Use the setup-and-timeline response in SKILL.md only after confirming Day 1's task. For an explicit setup-only request, say: "Setup complete. The dedicated browser, email, and SMS access are ready. Both days remain unstarted." If SMS is disabled, report that instead.

## Resume and recovery

Reuse saved connections and inbox assignments. Refresh expired tokens automatically; retry reads after transient failures. Request login only for missing/rejected authentication. Check access and balance again before Day 2 registration and before an SMS purchase.

A shared `.connections/agentmail-signup.json` records the signup intent. The vault retains the key and inbox binding so a crash after saving can recover them. An unresolved intent without its key blocks another signup. Preserve these records and reconcile the existing result.

AgentMail onboarding: https://docs.agentmail.to/agent-onboarding
