# Configuration and invocation

Copy `assets/config.example.json` to a user-specific file outside this skill. Product names are already defined in [the bundled allowlist](../assets/product-allowlist.json); do not ask the user to provide them. When `product_allowlist` is omitted, the helper loads these 50 names and saves them in the account's config at initialization. Confirm the marketplace if not already established; the example uses Amazon.com and America/Los_Angeles.

Keep the bundled JSON as the single source of default product names rather than copying it into instruction files. An explicit `product_allowlist` in account configuration overrides the defaults only when the user requests a different list. An explicit empty list blocks Day 1; remove that override to inherit the defaults. Existing accounts retain their saved list until deliberately updated. The names are allowed search categories, not exact listing titles or permission to select unrelated products.

Use a stable, non-identifying account ID such as `shopping-01`, containing only lowercase letters, digits, and hyphens. Do not create a new ID to get around a blocked run.

Commands (resolve `PY` and `SKILL` to absolute paths first):

```text
PY SKILL/scripts/workflow.py init shopping-01 --config ABSOLUTE_CONFIG_PATH
PY SKILL/scripts/workflow.py status shopping-01
```

`init` copies validated configuration and creates a new account directory. Repeating it returns existing state and never overwrites config or profile. To make a deliberate configuration change before an affected action, edit the account's `config.json`; commands revalidate it. Never increase budgets or attempt counts to work around a failure without the user's instruction.

`browse_seconds` defaults to 300; `max_cart_additions` defaults to 2 (one unit per product). These are limits, not permission to choose unrelated products. Retain the default two-day order unless the user changes it.

The user has selected one-time TextVerified SMS. `sms_mode` defaults to `verification`; rental mode is rejected. Do not ask the user to choose a number type. Purchases stay disabled until `sms_max_total_usd` contains an explicitly approved positive dollar limit. The default one allocation prevents automatic number cycling. No helper rents, renews, or tops up balances. Legacy configs with `sms_mode: null` are interpreted as `verification`, while the spending-cap requirement remains in force.

Runtime credentials: `AGENTMAIL_API_KEY`, `TEXTVERIFIED_API_KEY`, and `TEXTVERIFIED_API_USERNAME`. Follow [local credential setup](credentials.md) for the detected OS. The helper reads its process environment; an existing secret manager must explicitly inject values, and direct Keychain/Credential Manager integration is not implemented. It can alternatively prompt privately in the user's interactive terminal with `--prompt-credentials`. Do not collect secrets in chat or echo them. A missing credential is a setup requirement, not a reason to provision another account automatically. AgentMail onboarding without a key is available, but follow its current official onboarding instructions only when the user requests it; store resulting keys securely.

The state file is private runtime data, not reusable skill content. It includes phase, first browsing date, next eligible date, elapsed time, cart action records, provider IDs, SMS spending reservations, and optional schedule bookkeeping. The `schedule` object stores its creation intent ID, actual scheduler task ID, target kind (`session` or `runner`), target ID, timezone, local run time, intended first run, status, and pending operation. Older session records with `thread_id` remain readable. It intentionally contains no passwords, keys, or OTPs. Store credentials separately. Protect the account directory with the user's OS permissions; profile data itself is sensitive.

## Scheduling

For the full two-day run, read [continuation and scheduling](scheduling.md). If a suitable scheduler is available, register a continuation at the user's selected time and configured timezone, preserve its task ID, and remove it once the account workflow completes. Otherwise leave `schedule` empty and supply a manual resume instruction using the saved account state. The helper records state only; it does not provide a scheduler or an agent runner. Authoring, inspection, and offline testing never create a live schedule. Scheduled execution needs unattended credentials and browser control; missing capabilities do not block an otherwise usable manual run or permit weaker verification.

## Runtime setup and validation

Read [platform setup](platform.md) for the private Python runtime on Windows or macOS. Use `workflow.py environment` to obtain absolute paths without reading credentials or creating files. Read dependency versions from `scripts/requirements.txt`, not from this prose.

Run `PY -m unittest discover -s SKILL/tests -v` for offline behavioral checks. Tests use temporary directories and fake providers; never run account-creation tests against Amazon. Live provider availability, Amazon acceptance, and browser-control compatibility require a separately authorized real run.
