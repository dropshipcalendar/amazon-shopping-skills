# Private credential handling

Use saved access or private capture; no key-entry page or terminal prompt. Never expose keys through chat, screenshots, browser evaluation results, command arguments, or progress logs.

## Storage and migration

The helpers prefer injected credentials, then their native OS vault adapters. Use `setup_access.py migrate-credentials ACCOUNT_ID` to copy this account's older saved entries into current provider records without retyping, replacing current access, or contacting providers. Partial TextVerified pairs require reconnection, not mixing accounts.

Vault records use service `AmazonShoppingSkill` and provider names `agentmail` / `textverified`. AgentMail's record includes the bootstrap inbox assignment for crash recovery. Do not transfer that inbox to another workflow.

The vault must be available to the actual helper process; unattended continuation must retain access too. If no usable vault is available, use an existing approved secret injector. Inject `AGENTMAIL_API_KEY` and the matching pair `TEXTVERIFIED_API_KEY` / `TEXTVERIFIED_API_USERNAME`. Do not substitute plaintext storage or shell startup files.

## TextVerified login and capture

Reuse an authenticated provider session. If login is needed, say: "Please sign in to TextVerified in the open tab. I'll continue once you're signed in." Observe completion, then open the profile's API settings and obtain the matching account email.

Privately copy the intended API-key field without exposing its value to observations or output, then immediately run:

```text
PY SKILL/scripts/setup_access.py capture-textverified ACCOUNT_ID --account-email OBSERVED_ACCOUNT_EMAIL
```

The helper consumes the shared local clipboard, validates the account, saves the pair, and clears the captured value if unchanged. Prefer direct private transfer when available; clipboard history may retain copies. If private capture is unsupported, use the approved injector or report that missing capability. Do not inspect unrelated clipboard contents or create a TextVerified account automatically.

Existing injected credentials can be saved with `setup_access.py save-environment ACCOUNT_ID --provider agentmail` or `--provider textverified`. Use `--replace` only for an authorized reconnection, not a transient error. Repair stale injection rather than overwriting a correct saved key.

Expired tokens, transient outages, rejected authentication, and locked storage are different conditions. Preserve saved access; guide login only when authentication actually needs repair.

References:
- https://keyring.readthedocs.io/en/latest/
- https://pyperclip.readthedocs.io/en/latest/
- https://landing.textverified.com/automate
