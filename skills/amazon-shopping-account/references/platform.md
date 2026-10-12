# Detect and keep the execution computer

Read only the instructions for the detected OS. Resolve this skill directory from its actual location; do not copy the author's username or paths. Prefer the current computer when its capabilities are sufficient. Linux is supported; its presence alone is not a reason to switch to a connected Windows or Mac computer. Select one computer before initialization and keep both days, the state files, and the dedicated browser profile there.

Use a known Python 3.11+ interpreter to run `scripts/workflow.py environment`. This read-only command reports the OS, data/runtime paths, candidate browser executables, and whether Linux display variables are present. It does not read credentials or create files. OS values are `win32`, `darwin`, and `linux`. Report missing prerequisites rather than claiming the workflow can run.

| Item | Windows | macOS | Linux |
|---|---|---|---|
| Data directory | `%LOCALAPPDATA%/AmazonShoppingSkill` | `~/Library/Application Support/AmazonShoppingSkill` | `$XDG_DATA_HOME/AmazonShoppingSkill`, default `~/.local/share/AmazonShoppingSkill` |
| Private interpreter | `runtime/Scripts/python.exe` under data directory | `runtime/bin/python` under data directory | `runtime/bin/python` under data directory |
| Account folder | `accounts/ACCOUNT_ID` under data directory | Same | Same |
| Browser discovery | Chrome under Program Files or LocalAppData | Chrome in system or user Applications | Chrome/Chromium on `PATH`, then common `/usr/bin`, `/opt/google/chrome`, and `/snap/bin` locations |
| Reopen launcher | `open-browser.cmd` | `open-browser.command` | `open-browser.sh` |

Use `environment`/`status` output as authoritative for paths. Linux ignores empty or relative `XDG_DATA_HOME` values. Expand home-directory references and quote paths containing spaces. The configured account timezone controls the two-day schedule on every OS.

## Private runtime

If the reported interpreter exists, reuse it. Otherwise create a venv with a known Python 3.11+ executable. During authorized setup, ensure the pinned `scripts/requirements.txt` is installed in that private runtime, including when updating an older installation that lacks the secure-storage or clipboard dependencies. Do not install dependencies into system Python or edit the user's shell profile.

Windows PowerShell pattern (resolve `SKILL` and interpreter from observed paths):

```powershell
python -m venv "$env:LOCALAPPDATA\AmazonShoppingSkill\runtime"
& "$env:LOCALAPPDATA\AmazonShoppingSkill\runtime\Scripts\python.exe" -m pip install -r "SKILL\scripts\requirements.txt"
```

macOS shell pattern:

```sh
python3 -m venv "$HOME/Library/Application Support/AmazonShoppingSkill/runtime"
"$HOME/Library/Application Support/AmazonShoppingSkill/runtime/bin/python" -m pip install -r "SKILL/scripts/requirements.txt"
```

Linux shell pattern using the data directory returned by `environment`:

```sh
python3 -m venv "DATA_DIRECTORY/runtime"
"DATA_DIRECTORY/runtime/bin/python" -m pip install -r "SKILL/scripts/requirements.txt"
```

Replace `SKILL` and `DATA_DIRECTORY` with observed absolute paths before execution. If the chosen Python lacks venv/pip support or cannot install dependencies, report the prerequisite. Avoid retrying with elevated permissions or another global installation. Run subsequent commands with the returned private interpreter.

## Linux browser and cloud prerequisites

The built-in launcher opens a graphical Chrome/Chromium instance. It requires an existing X11 or Wayland session (`DISPLAY` or `WAYLAND_DISPLAY`), which may be a virtual display. A reported variable is a hint, not proof that the agent can see or control the browser. Check the live window/session and its Profile Path.

If the computer provides a separate browser-control service, use its documented launch/attach capability with the exact dedicated `--user-data-dir` returned by `workflow.py profile ACCOUNT_ID`. A shell-only or ephemeral default browser session is insufficient. The helper does not create a display server or supply browser automation.

For a browser executable at a custom location:

```text
PY SKILL/scripts/workflow.py launch ACCOUNT_ID --browser-path ABSOLUTE_EXECUTABLE_PATH
```

The override must name an existing executable, not a command with flags. Discovery and launch do not install a browser. Keep the browser sandbox enabled; if launch fails due to user, container, or sandbox configuration, report the missing capability and use a supported environment rather than disabling browser protections.

Before Day 1 on a cloud computer, verify that the skill files, account data directory, and browser profile persist through Day 2, including after a restart. Configure `XDG_DATA_HOME` to a verified absolute persistent directory before initialization if necessary. Resume with the same environment. Do not assume `/tmp`, a container's writable layer, or its home directory persists. Do not transfer an in-progress browser profile between operating systems as a workaround.

Offline tests exercise all platform branches, including executable shell launchers on Linux. They do not prove live browser control, cloud persistence, provider availability, or account acceptance on a particular machine.

Sources checked 2026-10-12:
- https://chromium.googlesource.com/chromium/src/+/HEAD/docs/user_data_dir.md
- https://www.chromium.org/developers/creating-and-using-profiles/
- https://specifications.freedesktop.org/basedir/latest/

## Secure storage and private capture

The pinned runtime includes `keyring` and `pyperclip`; [credential setup](credentials.md) selects only native secure backends. Windows uses Credential Manager, macOS Keychain, and Linux Secret Service. On Linux, verify an unlocked vault and its D-Bus session are available to both interactive and scheduled processes. Otherwise use an existing approved secret injector; never install plaintext-keyring fallbacks or persist an unlock password in scripts. Clipboard capture additionally needs a shared working clipboard; some Linux environments require a supported clipboard utility. If unavailable, use a direct private transfer or approved secret injection, never expose the key to compensate.
