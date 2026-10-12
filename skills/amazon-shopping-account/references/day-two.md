# Day 2: registration

Use the original verified profile. Inspect the live page first: if already signed in to the intended account, verify completion rather than registering again. Stop if another person's account is shown; do not enter account recovery.

1. Before new registration, run `setup_access.py signup-start ACCOUNT_ID --service EXACT_RETURNED_SERVICE_NAME` using the current Amazon shopping service. It checks email access, SMS readiness, completed Day 1, and the eligible date. With a saved SMS opt-out, omit `--service`; a later phone requirement is a blocker. For readiness failures, inspect `phone-check` results without raising saved limits.
2. If already in `signup`, reconcile the live form and any allocated number before continuing. Reuse the assigned inbox and user's name. Let the user enter the password directly or use their authorized secret manager.
3. Complete the observed form. Retrieve pending email verification through [email](email.md); use [one-time SMS](phone.md) only when the form requests a phone number.
4. After an uncertain submission, inspect the page before retrying. Stop for account restrictions rather than changing identities or connection settings.
5. Confirm the intended signed-in identity and inspect the cart without assuming guest items transferred. Do not automatically replace missing items.
6. Record `workflow.py signup-complete ACCOUNT_ID --evidence BRIEF_OBSERVED_CONFIRMATION`. Remove any saved schedule using [schedule cleanup](scheduling.md).

Report the outcome briefly, with the profile launcher and any remaining user action. Keep passwords and verification codes out of state and chat.
