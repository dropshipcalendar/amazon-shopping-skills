# Provider credentials

Read during initial setup or a failed connection. No separate key-entry page, form, modal, or terminal prompt is used. Never ask for keys in chat or expose them in screenshots, command arguments, logs, or state files.

## Durable storage

Helpers read injected environment credentials first, then the OS vault through `scripts/secure_store.py`. Native backends are selected explicitly: Windows Credential Manager with local-machine persistence, macOS Keychain, and Linux Secret Service or KWallet. Plaintext, null, and automatically discovered third-party keyring backends are not accepted. A locked or unavailable vault is a setup requirement, not an absent credential or permission to create another account.

Vault entries use service `AmazonShoppingSkill` and provider names `agentmail` / `textverified`. Each provider's key and associated fields are saved together. AgentMail's bootstrap entry also retains its inbox assignment so a crash between the vault write and progress save cannot create a second inbox. Provider access is shared across runs for this OS user; inbox assignments and Chrome profiles remain per workflow. Do not move a bootstrap inbox to another workflow or automatically create another provider organization.

`setup_access.py migrate-credentials ACCOUNT_ID` reads only this account's previous account-scoped vault identifiers and copies missing provider records into the current store. It never enumerates the vault, replaces a current connection, deletes the previous entries, or contacts a provider. An incomplete previous TextVerified key/email pair needs reconnection and is never mixed with another account. Windows reads retain the existing hardened adapter and latest-value precedence; new writes use local-machine persistence.

The OS vault protects secrets at rest; it does not isolate them from other programs running as the same authorized user. Linux requires an available, unlocked Secret Service and the correct D-Bus session. A display alone is insufficient. With an approved external secret injector, supply `AGENTMAIL_API_KEY` and the matching pair `TEXTVERIFIED_API_KEY` / `TEXTVERIFIED_API_USERNAME` to the actual process. Partial TextVerified overrides are rejected to avoid mixing accounts. Do not write keys to shell startup files or user environment settings as a persistence workaround.

## Capture existing access

Prefer saved access. If TextVerified is not connected, reuse the user's signed-in provider session. If needed, say only: "Please sign in to TextVerified in the open tab. I'll continue once you're signed in." Observe login completion before proceeding. Do not create a TextVerified account or reset its password automatically.

Navigate to the profile's API settings. Obtain the matching account email from the authorized page. Use its API-key Copy control, or privately select and copy that exact field, without returning the key through browser evaluation, accessibility snapshots, screenshots, tool output, or chat. Immediately run:

```text
PY SKILL/scripts/setup_access.py capture-textverified ACCOUNT_ID --account-email OBSERVED_ACCOUNT_EMAIL
```

The helper consumes the local clipboard internally, validates the account through a read-only API request, saves the pair in the vault, and clears the captured clipboard value if it has not changed. The browser and helper must share that clipboard. Copy only the intended field immediately before capture; never inspect an unrelated clipboard. Clipboard managers may retain history; prefer an available direct browser-to-vault secret transfer. If the computer tools cannot copy privately, do not reveal the value to work around it: use the approved secret injector or report the missing private-transfer capability once.

Existing injected access can be persisted without revealing it:

```text
PY SKILL/scripts/setup_access.py save-environment ACCOUNT_ID --provider agentmail
PY SKILL/scripts/setup_access.py save-environment ACCOUNT_ID --provider textverified
```

These commands never request input. They do not overwrite a different saved credential unless `--replace` is explicitly supplied during an authorized reconnection. Do not rotate keys or replace an established provider connection merely because a request failed. Injected variables override stored values; repair a stale injection instead of overwriting the correct vault entry.

## Resume and scheduling

Run connection checks using a fresh helper process, and through the actual scheduled runner when one is selected. It must use the same OS identity and unlocked vault session, or receive the approved secret injection. Saving a key in an interactive desktop vault does not establish that an unattended runner can unlock it. Never promise automatic Day 2 execution without verifying this capability.

Expired TextVerified bearer tokens are refreshed by the SDK. Authentication rejection needs reconnection; permission denial needs account-access review; rate limits and outages need bounded read retries. None means create another provider account. A saved `ready` timestamp is historical, not proof of current access.

Sources checked 2026-10-12:
- https://keyring.readthedocs.io/en/latest/
- https://pyperclip.readthedocs.io/en/latest/
- https://landing.textverified.com/automate
