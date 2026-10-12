# Credential entry on Windows, macOS, or Linux

Use the platform detected by `workflow.py environment`. Never ask users to paste secrets into chat or show credential values in screenshots, tool output, shell command arguments, or logs.

Only three variable names are relevant:
- `AGENTMAIL_API_KEY` for the email helper.
- `TEXTVERIFIED_API_KEY` and `TEXTVERIFIED_API_USERNAME` for the SMS helper.

The helper reads its own process environment. It does not automatically read macOS Keychain or Windows Credential Manager. An existing credential manager is usable only through its approved environment-injection mechanism. Do not imply that saving a key in either OS vault alone makes it available to this skill.

## Hidden terminal entry

If the user has not configured an injector, the provider helper supports hidden, nonpersistent prompts. Run it in a user-operated interactive local terminal, not an agent-captured stdin session:

```text
PY SKILL/scripts/providers.py email-create ACCOUNT_ID --prompt-credentials
PY SKILL/scripts/providers.py phone-services ACCOUNT_ID --prompt-credentials
```

Prepare a fully resolved copy-paste command for the user: replace `PY`, `SKILL`, and `ACCOUNT_ID` with the correct paths and account rather than making the user edit placeholders. On Windows use PowerShell's `&` to execute the quoted interpreter path. On macOS and Linux quote the interpreter and script paths. The user pastes values directly into the hidden prompt. Only credentials missing from the process environment are requested. Input is rejected if no interactive terminal or hidden entry is available; there is no echoed-input fallback. Values are available only to that helper process, are not saved, and must be supplied again on another invocation unless an injector is configured. This is a terminal entry option, not a graphical setup wizard.

Run only the operation appropriate to the current workflow phase. These commands reject credential prompting outside Day 2 signup. API output may contain a private verification message required to complete signup; keep it out of final reports.

## Windows environment setup

For users choosing persistent user environment variables, direct them to Start -> "Edit environment variables for your account" -> User variables -> New. Have them enter the three names and values privately. Do not request a screenshot containing values. Restart the app or process that launches helpers so its children inherit the updated environment; if necessary use the supported launcher for that app. These are environment variables, not an encrypted credential vault.

## macOS environment setup

An exported variable in one Terminal session is inherited by helper commands launched from that session, not by an unrelated Terminal or an already-running desktop app. Use hidden local entry above for an immediate operation, or a user-approved secret-manager launcher that injects the variables into the process running this workflow. Do not tell the user that editing `.zshrc` or restarting a Finder-launched app automatically supplies these values. Do not persist raw API keys in shell startup files or shell history.

## Linux and cloud environment setup

Use the cloud computer's approved secret injection mechanism or an existing secret-manager launcher to provide values to the actual helper/agent process. An export in one terminal does not populate an unrelated browser service, scheduler, or future container. Do not write keys into shell startup files, a repository, or shell history. For an immediate supervised operation, the hidden prompt above works when a private interactive terminal is available; do not emulate it by typing secrets through captured tools.

For unattended Day 2 execution on any supported platform, verify that the actual scheduled process receives the environment through its approved launcher. Test credential presence or a read-only connection status, never print the values. A missing credential should produce an actionable setup message; do not provision a new provider account or substitute a different provider.

Sources checked 2026-10-12:
- https://support.apple.com/guide/terminal/use-environment-variables-apd382cc5fa-4f58-4449-b20a-41c53c006f8f/mac
- https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_environment_variables
