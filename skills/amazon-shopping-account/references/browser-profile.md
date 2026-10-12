# Dedicated persistent browser profile

Use `workflow.py profile ACCOUNT_ID` to obtain the user-data directory, expected Profile Path, and launch arguments. Use `workflow.py launch ACCOUNT_ID` to open the dedicated browser; retain the returned launcher for reopening it. The helpers handle platform paths and launch formats. Supply `--browser-path ABSOLUTE_EXECUTABLE_PATH` only for an observed executable outside discovery.

Use whichever supported browser or native computer controls can operate this exact instance. If the helper launcher is unavailable, an existing browser-control service may launch with the returned user-data directory and arguments. Try suitable available controls before reporting a missing capability.

Read Profile Path at `chrome://version` and record it with `workflow.py verify-profile ACCOUNT_ID --observed-path EXACT_OBSERVED_PATH`. It must match this account's `chrome-data/Default`; canonical path aliases are acceptable. A launcher result or old verification flag does not establish current browser control.

Attach to an existing instance using this directory rather than opening concurrent owners. Keep Chrome Sync off and do not import personal cookies. Confirm Amazon is signed out for Day 1; inspect current sign-in state before Day 2 submission.

Keep the profile and state on the original persistent computer through both days. Do not clear cookies or change proxies/extensions as part of setup. Profile separation does not isolate data from other processes running as the same OS user.

References:
- https://chromium.googlesource.com/chromium/src/+/HEAD/docs/user_data_dir.md
- https://www.chromium.org/developers/creating-and-using-profiles/
