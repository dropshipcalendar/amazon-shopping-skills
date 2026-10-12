# Defaults and overrides

Use existing settings first. New workflows default to `shopping-01`, Amazon.com, and the detected local IANA timezone. Ask for a timezone only if detection fails. The bundled [50-product allowlist](../assets/product-allowlist.json) is automatic; do not request product names.

| Setting | Default / meaning |
|---|---|
| `browse_seconds` | 300 active seconds |
| `max_cart_additions` | Two distinct matching products, quantity one |
| `sms_enabled` | True; preserve an existing false value |
| `sms_mode` | `verification`; legacy null normalizes to this |
| `sms_min_balance_usd` | `"0.75"`; live readiness rules are in [phone](phone.md) |
| `sms_max_total_usd` | Null until the user approves a positive total cap |
| `sms_max_allocations` | One |

A saved positive cap remains the spending authorization. Never increase spending/attempt limits or change an opt-out to pass a check. Keep marketplace/timezone fixed after Day 1 starts and SMS settings fixed after an allocation attempt.

Explicit user-requested product lists override the bundle. An empty list blocks browsing; remove that override to inherit the defaults. Categories permit relevant searches, not unrelated products.

For advanced initialization, use `workflow.py init ACCOUNT_ID --config ABSOLUTE_CONFIG_PATH` with a copy of `assets/config.example.json` outside the skill. The example timezone is America/Los_Angeles. Repeated initialization preserves existing state. Account IDs use lowercase letters, digits, and hyphens.

Config and state paths come from `workflow.py status`. State retains phase, dates, browsing time, cart intents, inbox/SMS identifiers, readiness checks, and schedule bookkeeping. Keep credentials separately and retain this state across runs.
