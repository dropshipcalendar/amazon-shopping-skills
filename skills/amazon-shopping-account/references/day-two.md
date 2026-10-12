# Day 2: one shopping account

1. Reopen and verify the original dedicated profile. Run `workflow.py signup-start ACCOUNT_ID`; it refuses to proceed before completed Day 1 and its next calendar date. A late invocation can proceed after that date. Do not change the clock or saved date to bypass this check.
2. Inspect the live Amazon page. If already signed in to the intended account, verify completion instead of resubmitting registration. If a different account or an existing registration is indicated, stop and report it; do not enter account recovery or create an alternate identity.
3. Read `email.md` and create/reuse the assigned inbox. Use the user's provided name. Let the user enter a password directly or use their authorized secret manager. Never save the password in the config, state, or chat.
4. Follow the current visible registration form. Use the exact assigned email. Record only fields and results needed to resume, without secrets. Do not assume button labels or mandatory fields from previous runs.
5. Handle a pending email verification through `email.md`. Only if the form requests a phone number, read `phone.md` and use a one-time TextVerified SMS verification. Do not rent, renew, or upgrade a number.
6. Treat a timeout after submission as uncertain. Inspect the current page and intended account state before any retry. Stop for account restrictions; do not rotate numbers, profiles, addresses, or networks to continue.
7. Confirm a signed-in page showing the intended email/account identity. Inspect the cart without assuming the guest cart transferred. Do not rerun Day 1 or replace missing cart items automatically.
8. Record `workflow.py signup-complete ACCOUNT_ID --evidence BRIEF_OBSERVED_CONFIRMATION`. This command records the agent's observation, not an independent verification. It marks an existing automation as needing removal; it does not delete the remote schedule. Follow `scheduling.md` to remove that exact automation and record confirmed removal. If cleanup fails, keep the workflow complete, report cleanup pending, and retry only cleanup on a later invocation.
9. Report actual results and the profile shortcut. State that the one-time number is temporary and future access is not guaranteed, and identify any remaining user action.

The skill authoring request alone authorizes no live signup, paid number allocation, or scheduling. A later request to run it is the execution scope. Use existing authorization without repeatedly asking for the same action, while honoring configured spending and attempt limits.
