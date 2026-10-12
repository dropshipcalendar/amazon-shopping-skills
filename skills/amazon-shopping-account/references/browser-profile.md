# Dedicated persistent Chrome session

The helper creates `chrome-data` inside the account directory, separate from personal Chrome data. This is browser-data separation, not a VM, a different network identity, or protection from another process running as the same OS user.

1. Run `workflow.py profile ACCOUNT_ID` to obtain the exact user-data directory and launch arguments. Never substitute the default Chrome profile or copy existing cookies.
2. Run `workflow.py launch ACCOUNT_ID`; it detects Windows, macOS, or Linux, locates installed Chrome (or Chromium on Linux), and opens `chrome://version` with the dedicated `--user-data-dir`. It creates `open-browser.cmd` on Windows, executable `open-browser.command` on macOS, or executable `open-browser.sh` on Linux. Use the returned shortcut path, never an assumed path. For a browser outside discovered locations, use `launch ACCOUNT_ID --browser-path ABSOLUTE_EXECUTABLE_PATH` with its observed location; do not open the personal profile as a fallback.
3. Use the browser or computer-control tools available to this agent on the detected OS. Mouse/keyboard control and screenshots are sufficient if they let you identify and operate this exact Chrome instance; a browser integration is optional. Select a uniquely observed window. If no available tool can control this profile, report the missing capability; a working Chrome launcher alone does not imply working browser automation. Follow the selected tool's documented connection and permission requirements.
4. Read Profile Path on `chrome://version`. It must equal `chrome-data/Default` for this account (canonical path aliases are acceptable). Run `workflow.py verify-profile ACCOUNT_ID --observed-path EXACT_OBSERVED_PATH`. This records the observation; the command cannot inspect the browser for you.
5. Keep this profile signed out of Chrome Sync, with no personal-data import. On Day 1 confirm Amazon is signed out. Before Day 2 resume, inspect whether signup already succeeded to avoid duplicate submission.

Do not launch two independent automation owners against the same directory. If Chrome is already running there, attach to that exact observed instance. The helper's file lock serializes state commands; it is not a lock over the whole UI session. Coordinate one owner per account.

On Linux, the launcher needs an existing X11 or Wayland session, including a usable virtual display. A shell-only machine is not enough for this launcher. An existing browser-control service may instead start or attach to a browser with the exact arguments returned by `profile`; verify its live Profile Path before acting. Do not silently attach to its default profile. If the browser reports sandbox or permission failures, use a supported environment rather than disabling its sandbox.

The returned platform-specific shortcut reopens the same profile. On macOS it launches Chrome directly, avoiding an already-running default instance ignoring the custom profile arguments. Do not clear cookies, delete the directory, install fingerprint-altering extensions, or modify proxies as part of this workflow.

Sources checked 2026-10-12:
- https://www.chromium.org/developers/creating-and-using-profiles/
- https://chromium.googlesource.com/chromium/src/+/HEAD/docs/user_data_dir.md
- https://support.google.com/chrome/answer/2364824
