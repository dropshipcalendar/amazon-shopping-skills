# Dedicated persistent Chrome session

The helper creates `chrome-data` inside the account directory, separate from personal Chrome data. This is browser-data separation, not a VM, a different network identity, or protection from another process running as the same OS user.

1. Run `workflow.py profile ACCOUNT_ID` to obtain the exact user-data directory and launch arguments. Never substitute the default Chrome profile or copy existing cookies.
2. Run `workflow.py launch ACCOUNT_ID`; it detects Windows or macOS, locates installed Chrome, and opens `chrome://version` with the dedicated `--user-data-dir`. It creates `open-browser.cmd` on Windows or executable `open-browser.command` on macOS. Use the returned shortcut path, never an assumed path. If Chrome is installed elsewhere, inspect its actual location and use a supported app launcher with the exact reported profile arguments; do not open the personal profile as a fallback.
3. Use a supported browser-control surface that can actually reach this instance. On Windows, use the available Windows `computer-use` skill and its required runtime/confirmation guidance. On macOS, discover an available macOS-compatible browser or computer-use tool and follow its documented capabilities; the Windows `@oai/sky` runtime is not a Mac substitute. Select a uniquely observed window. If no tool can control this exact profile, stop and explain the missing capability; a working Chrome launcher alone does not imply working browser automation. Do not improvise an unsupported debugging connection or request broad OS permissions that the selected tool does not require.
4. Read Profile Path on `chrome://version`. It must equal `chrome-data/Default` for this account (canonical path aliases are acceptable). Run `workflow.py verify-profile ACCOUNT_ID --observed-path EXACT_OBSERVED_PATH`. This records the observation; the command cannot inspect the browser for you.
5. Keep this profile signed out of Chrome Sync, with no personal-data import. On Day 1 confirm Amazon is signed out. Before Day 2 resume, inspect whether signup already succeeded to avoid duplicate submission.

Do not launch two independent automation owners against the same directory. If Chrome is already running there, attach to that exact observed instance. The helper's file lock serializes state commands; it is not a lock over the whole UI session. Coordinate one owner per account.

The returned platform-specific shortcut reopens the same profile. On macOS it launches Chrome directly, avoiding an already-running default instance ignoring the custom profile arguments. Do not clear cookies, delete the directory, install fingerprint-altering extensions, or modify proxies as part of this workflow.

Sources checked 2026-10-12:
- https://www.chromium.org/developers/creating-and-using-profiles/
- https://chromium.googlesource.com/chromium/src/+/HEAD/docs/user_data_dir.md
- https://support.google.com/chrome/answer/2364824
