# Configuration and invocation

For the normal installation experience follow [private setup](setup.md): `setup.py prepare` initializes settings, retains existing accounts, and creates a reopenable private configuration launcher. New accounts default to `shopping-01`, Amazon.com, a locally detected IANA timezone, and the bundled product allowlist. Show these choices without a chat questionnaire. If detection fails, ask for the missing timezone. Setup may collect credentials now or defer them to Day 2.

Advanced/manual initialization still accepts `assets/config.example.json` through `workflow.py init ACCOUNT_ID --config ABSOLUTE_PATH`. The example timezone is America/Los_Angeles, not a universal detected default. Config files must never contain credentials.

Commands (replace PY, SKILL, and ACCOUNT_ID with actual values):

```text
PY SKILL/scripts/setup.py prepare ACCOUNT_ID
PY SKILL/scripts/setup.py launch ACCOUNT_ID
PY SKILL/scripts/setup.py status ACCOUNT_ID
PY SKILL/scripts/workflow.py status ACCOUNT_ID
```

Account IDs contain lowercase letters, digits, and hyphens and must be stable. Do not create a replacement ID to circumvent a blocked run. The prepared ID is fixed; a user can select another ID before preparation through the command argument. All per-account files live outside the skill under the platform data directory returned by the helpers. Existing configuration and progress are never reset by prepare/init.

## Products and time

When `product_allowlist` is omitted, initialization copies all 50 names from [the bundled allowlist](../assets/product-allowlist.json). Use them automatically; do not ask the user for product names. Explicit user-requested overrides are retained. An empty override blocks Day 1; remove it to inherit the defaults. Categories are not exact listing titles or permission to select unrelated products.

`browse_seconds` defaults to 300; `max_cart_additions` defaults to 2, one unit per product. Follow the two-day order and [browser interaction](browser-interaction.md). Marketplace and timezone become fixed once Day 1 starts. Setup may not rewrite affected settings during an in-progress run.

## SMS defaults and authorization

`sms_enabled` defaults to true. `sms_mode` is `verification`; rental mode is rejected and legacy null modes normalize to verification. `sms_max_allocations` defaults to one. `sms_max_total_usd` defaults to null, meaning budget approval pending. It never means unlimited spending.

The user supplies and explicitly accepts a positive total cap through the interactive setup command or explicit instruction. The minimal credential form never changes or approves spending. A preexisting positive configured cap remains approved; a repeated setup never overwrites it or a saved opt-out. Once approved, do not request duplicate authorization for a required one-time verification within that limit. Amazon must request a phone during Day 2, credentials must be available, and the live quote must fit the remaining cap. Helpers retain all existing reservations and uncertain-purchase safeguards. Setup refuses budget or SMS-enablement changes after any allocation attempt. It never purchases credit, rents, renews, or automatically cycles numbers.

The SMS toggle is an option, not an independent spending authorization. `sms_enabled: false` blocks new SMS purchases. Retrieval/cancellation for an existing allocation remains available for reconciliation.

## Credentials and readiness

Follow [credentials](credentials.md). Every helper can use approved process-environment injection or the account's native OS credential store. Setup saves secrets only to that native store; it does not write them to `config.json` or `state.json`. Provider prompts remain available for supervised Day 2 operations.

Missing Day 2 credentials, an unavailable store, or a pending SMS cap do not block Day 1 preparation. `setup.py status` reports configuration and historical profile observation without contacting providers or accessing the vault. Add `--check-credentials` only when checking access is appropriate; this may prompt the OS and reports no values. Report Day 1 ready only after actual live browser/profile/signed-out checks. A saved phase or profile flag is not independent proof.

## Continuation

Read [scheduling](scheduling.md) for an authorized full run. The state retains phase, browsing date/time, cart intents, inbox/provider IDs, SMS reservations, and scheduler bookkeeping, with no passwords, keys, or OTPs. Scheduled execution must use the same persistent account root and profile and must prove access to credentials from its actual process. If input/unlocking is required, preserve progress and use manual continuation. Preparing, installing, or saving settings does not authorize either day or create a live schedule.

Offline validation:

```text
PY -m unittest discover -s SKILL/tests -v
```

Tests use temporary accounts and fake stores/providers. Native backend, GUI, browser, and scheduler access must be verified in the actual environment; simulated platform tests do not prove a live OS integration.
