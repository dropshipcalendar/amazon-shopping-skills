# Detect the host before setup

Read only the instructions for the detected host. Resolve the current skill directory from its actual location; never copy the original author's username or Windows paths onto another machine.

Use a known Python 3.11+ interpreter to run `scripts/workflow.py environment`. This read-only command reports the OS, absolute data/runtime paths, and candidate Chrome executables, without reading credential values. The OS is `win32` for Windows and `darwin` for macOS. If no suitable interpreter is available, report that setup prerequisite; do not claim the skill can run yet.

| Item | Windows | macOS |
|---|---|---|
| Data directory | `%LOCALAPPDATA%/AmazonShoppingSkill` | `~/Library/Application Support/AmazonShoppingSkill` |
| Private interpreter | `runtime/Scripts/python.exe` under data directory | `runtime/bin/python` under data directory |
| Account folder | `accounts/ACCOUNT_ID` under data directory | `accounts/ACCOUNT_ID` under data directory |
| Chrome candidates | Chrome executable under Program Files, Program Files (x86), or LocalAppData | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, then the same bundle under `~/Applications` |
| Reopen launcher | `open-browser.cmd` inside account folder | `open-browser.command` inside account folder |

Treat `environment`/`status` output as authoritative for paths. Expand the current user's home directory and quote paths containing spaces. The account's configured timezone controls the two-day schedule on either platform; do not replace it with the OS timezone.

## Private runtime

If the reported interpreter exists, use it. Otherwise create a venv with a known Python 3.11+ executable and install the pinned `scripts/requirements.txt` into it. Do not install dependencies into system Python or edit the user's shell profile.

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

Replace `SKILL` with the actual absolute skill directory before execution. If the chosen Python lacks venv support or cannot install dependencies, report the exact prerequisite. Avoid retrying with elevated permissions or another global installation.

Run all subsequent commands with the returned private interpreter. Chrome launching is implemented for Windows and macOS; browser interaction still requires a compatible tool attached to the dedicated session. Offline tests exercise both platform branches, but do not establish that native Mac UI automation is available on a particular machine.

Sources checked 2026-10-12:
- https://chromium.googlesource.com/chromium/src/+/HEAD/docs/user_data_dir.md
- https://www.chromium.org/developers/creating-and-using-profiles/
