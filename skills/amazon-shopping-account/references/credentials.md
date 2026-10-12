# Private credentials on Windows, macOS, and Linux

For first-time preparation read [setup](setup.md). Do not ask for secrets in chat, inspect credential-entry fields, take screenshots during entry, or place secrets in command arguments, logs, configuration, or skill files. The Amazon password is entered directly by the user on Amazon during Day 2; setup never stores it.

The provider fields are `AGENTMAIL_API_KEY`, `TEXTVERIFIED_API_KEY`, and `TEXTVERIFIED_API_USERNAME`. Credentials may be configured before Day 2, but provider operations remain restricted to Day 2 signup.

## Native storage

The private form and interactive setup command use `credential_store.py` and the pinned `keyring` package. Only these native backends are accepted:

| Platform | Storage | Prerequisite |
|---|---|---|
| Windows | Windows Credential Manager, local-machine persistence | Same Windows user context |
| macOS | Keychain | Supported Python build and access to the user's keychain |
| Linux | Secret Service or KWallet | Running, accessible service and its required session/libraries |

The service namespace includes the account ID and a hash of the resolved account directory, so separate accounts/data roots do not overwrite each other. Use the same root and OS user on both days. Blank form fields preserve stored values. Save updates only fields the user filled in. The advanced terminal setup requires explicit replacement confirmation. A partially failed multi-field save may have saved some credentials; inspect presence before retrying.

The helper refuses plaintext, null, unsupported, or arbitrary third-party backends. It may select an approved native backend from a keyring chain but never uses the chain's insecure fallbacks. Do not install `keyrings.alt` or create a plaintext `.env` as a workaround. Native storage protects credentials at rest; it does not isolate them from every process with the same OS-user privileges.

### Windows replacements and existing installations

Windows selects the supported native backend, then uses the Windows credential API to write one entry per field with `CRED_PERSIST_LOCAL_MACHINE`. Replacing a field overwrites that entry instead of leaving the old key in a duplicate. Older shared/compound entries remain readable; a successful save writes the new entry first, then removes that field's stale compound copy and legacy shared entry, if present. Other fields are preserved. A failed cleanup is reported as a failed save, so retry after resolving the vault error.

After updating an existing Windows installation, migrate all saved fields without retyping keys:

```text
PY SKILL/scripts/setup.py harden-credentials ACCOUNT_ID
```

Resolve the interpreter, skill path, and account ID as usual. This command accesses only the three known fields for that account, ignores environment overrides, preserves each latest saved value, writes local-machine entries, and removes superseded local duplicates. It prints only a count. It does not contact providers or change workflow settings. Read-only status does not migrate credentials. Untouched older entries retain their previous persistence until saved or migrated; changing local entries cannot recall copies already roamed or backed up. This migration is Windows-only; macOS and Linux continue using their existing native stores.

## Provider access

Every provider invocation checks its own process environment first, then the account's native store. Existing approved environment injection remains supported. Stored values are injected into that helper process only and restored/removed on exit. The CLI has no command that prints credentials.

Use `setup.py status ACCOUNT_ID --check-credentials` for a presence/access check. It reports configured, missing, locked, or unavailable and the source, without values. This can prompt the OS to unlock or authorize access: let the user handle it. Plain `status` does not access the vault. Presence is not proof that a provider accepts the credential; setup makes no provider requests.

## Manual fallback

When GUI setup is unavailable, give a fully resolved command for the user's own interactive terminal:

```text
PY SKILL/scripts/setup.py configure ACCOUNT_ID --prompt
```

Replace all paths and the account ID. Windows PowerShell requires `&` before the quoted interpreter path. This command can save settings without credentials even when native storage is unavailable.

When there is no usable native store, use approved environment injection or hidden provider prompts at the actual Day 2 operation:

```text
PY SKILL/scripts/providers.py email-create ACCOUNT_ID --prompt-credentials
PY SKILL/scripts/providers.py email-messages ACCOUNT_ID --after UTC_REQUEST_TIMESTAMP --prompt-credentials
PY SKILL/scripts/providers.py phone-services ACCOUNT_ID --prompt-credentials
```

These prompts run only in the user's interactive terminal, never agent-captured stdin. Hidden entry must be available; there is no echoed-input fallback. Prompted values last for that helper invocation only. Another invocation can require entry again if no native store or injector is configured. Do not imply that entering a key into one terminal makes it available to unrelated processes or future runs.

For unattended execution, verify access from the actual scheduled process under its OS user/session. A desktop-unlocked store is not proof that a background process can access it. If unlocking, secret entry, or the Amazon password requires the user, choose manual continuation. Do not change keychain permissions, security settings, or container privilege to remove the handoff.

Sources:
- https://keyring.readthedocs.io/en/latest/
- https://docs.python.org/3/library/getpass.html
