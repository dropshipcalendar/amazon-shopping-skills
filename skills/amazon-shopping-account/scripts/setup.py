"""Prepare local settings and collect credentials privately; no provider actions."""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import warnings
from zoneinfo import ZoneInfo

import credential_store
from workflow import Account, WorkflowError, stamp, validate_config, write_json


def detected_timezone():
    try:
        from tzlocal import get_localzone_name
        value = get_localzone_name()
        ZoneInfo(value)
        return value
    except Exception:
        raise WorkflowError("Timezone detection unavailable; supply --timezone with an IANA timezone") from None


def write_launcher(account, platform=None):
    platform = platform or sys.platform
    argv = [sys.executable, str(Path(__file__).resolve()), "--root", str(account.root), "open", account.account_id]
    if platform == "win32":
        if any(any(c in arg for c in ('"', '\r', '\n')) for arg in argv):
            raise WorkflowError("Unsupported character in setup launcher path")
        quoted = " ".join('"' + arg.replace('%', '%%') + '"' for arg in argv)
        path = account.path / "open-setup.cmd"
        path.write_text('@echo off\nsetlocal DisableDelayedExpansion\n' + quoted + '\n', encoding="utf-8")
    elif platform in ("darwin", "linux"):
        path = account.path / ("open-setup.command" if platform == "darwin" else "open-setup.sh")
        path.write_text("#!/bin/sh\nexec " + shlex.join(argv) + "\n", encoding="utf-8", newline="\n")
        path.chmod(0o700)
    else:
        raise WorkflowError("Setup supports Windows, macOS, and Linux")
    return path


def prepare(account_id="shopping-01", root=None, marketplace=None, timezone=None):
    account = Account(account_id, root)
    with account.locked(create=True):
        if account.state_path.exists():
            account.load()  # Never overwrite an existing run with defaults.
        else:
            config = {"timezone": timezone or detected_timezone()}
            if marketplace:
                config["marketplace"] = marketplace
            account.initialize(config)
        launcher = write_launcher(account)
    return account, launcher


def report(account, check_credentials=False):
    result = account.status()
    result.update(setup_status="prepared", provider_connection="not_tested",
                  day_one_readiness="requires_live_browser_check",
                  profile_observed=bool(account.state.get("profile_verified_at")),
                  setup_saved_at=account.state.get("setup_saved_at"))
    if account.state["phase"] in ("waiting_day_two", "signup", "complete"):
        result["day_one_readiness"] = "completed"
    if check_credentials:
        result["credentials"] = credential_store.status(account)
    return result


def save_settings(account, settings, credentials=None, approve_sms_budget=False, replace_credentials=False):
    allowed = {"marketplace", "timezone", "sms_enabled", "sms_max_total_usd"}
    if set(settings) - allowed:
        raise WorkflowError("Unsupported setup setting")
    with account.locked():
        account.load()
        if account.state["phase"] == "complete":
            raise WorkflowError("Account setup is complete; existing settings were preserved")
        new = validate_config(account.config | settings)
        for key in ("marketplace", "timezone"):
            if new[key] != account.config[key] and account.state["day_one_date"]:
                raise WorkflowError("Marketplace and timezone cannot change after Day 1 starts")
        cap_changed = new["sms_max_total_usd"] != account.config["sms_max_total_usd"]
        if cap_changed and new["sms_max_total_usd"] is not None and not approve_sms_budget:
            raise WorkflowError("Accept the displayed SMS spending limit before saving it")
        if account.state["sms"] and (cap_changed or new["sms_enabled"] != account.config["sms_enabled"]):
            raise WorkflowError("SMS settings cannot change after an allocation attempt")
        credential_store.save(account, credentials or {}, replace=replace_credentials)
        write_json(account.config_path, new)
        account.config = new
        account.state["setup_saved_at"] = stamp()
        account.save()
    return report(account)


def hidden_input(label):
    if sys.stdin is None or not sys.stdin.isatty():
        raise WorkflowError("Use a user-operated interactive terminal for credential entry; never send secrets in chat")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            return getpass.getpass(label)
        except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
            raise WorkflowError("Private credential entry unavailable or cancelled") from None


def terminal_setup(account):
    if sys.stdin is None or not sys.stdin.isatty():
        raise WorkflowError("Run the setup command in your own interactive terminal")
    print("Private setup. Blank fields preserve saved values. API keys are stored in the native OS credential store.")
    print("No inboxes, phone numbers, browsing, or schedules are created.")
    settings = {}
    for key, label in (("marketplace", "Marketplace URL"), ("timezone", "IANA timezone")):
        value = input(f"{label} [{account.config[key]}]: ").strip()
        if value:
            settings[key] = value
    enabled = input(f"Enable one-time SMS if required? [{('yes' if account.config['sms_enabled'] else 'no')}]: ").strip().lower()
    if enabled:
        if enabled not in ("yes", "no"):
            raise WorkflowError("Enter yes or no for SMS enablement")
        settings["sms_enabled"] = enabled == "yes"
    value = input(f"Total SMS limit USD [{account.config['sms_max_total_usd'] or 'not approved'}]; blank keeps it: ").strip()
    approved = False
    if value:
        candidate = validate_config(account.config | settings | {"sms_max_total_usd": value})
        value = str(candidate["sms_max_total_usd"])
        approved = input(f"Allow up to USD {value} total, only when Amazon requires SMS? Type yes: ").strip().lower() == "yes"
        if not approved:
            raise WorkflowError("Spending limit was not accepted; settings unchanged")
        settings["sms_max_total_usd"] = value
    credentials = {}
    if input("Save provider credentials privately now? [no]: ").strip().lower() == "yes":
        for name in credential_store.NAMES:
            entered = hidden_input(f"{name} (hidden; blank preserves/skips): ")
            if entered:
                credentials[name] = entered
    replace = bool(credentials) and input("Replace any existing credentials entered above? [no]: ").strip().lower() == "yes"
    result = save_settings(account, settings, credentials, approved, replace)
    credentials.clear()
    print(json.dumps(result, ensure_ascii=False))


def gui_setup(account):
    # Import lazily: Tk is not bundled with every Python distribution.
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
        window = tk.Tk()
    except Exception:
        raise WorkflowError("Local setup window unavailable; run setup.py configure ACCOUNT_ID --prompt in your own terminal") from None
    window.title("Amazon shopping — private setup")
    window.resizable(True, False)
    frame = ttk.Frame(window, padding=20)
    frame.grid(sticky="nsew")
    frame.columnconfigure(1, weight=1)
    ttk.Label(frame, text=f"Account: {account.account_id}", font=("TkDefaultFont", 13, "bold")).grid(row=0, columnspan=2, sticky="w")
    ttk.Label(frame, text="Day 1: browse for five minutes when authorized. Day 2: register and verify in the same profile on the next eligible day. Credentials can be configured now or before Day 2.", wraplength=580).grid(row=1, columnspan=2, sticky="w", pady=(6, 14))
    fields = {}
    for row, (key, label) in enumerate((("marketplace", "Marketplace URL"), ("timezone", "IANA timezone"), ("sms_max_total_usd", "Total SMS limit (USD)")), 2):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        fields[key] = tk.StringVar(value=str(account.config[key] or ""))
        ttk.Entry(frame, textvariable=fields[key], width=46).grid(row=row, column=1, sticky="ew")
    sms = tk.BooleanVar(value=account.config["sms_enabled"])
    approve = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text="Enable one-time SMS when Amazon requires it", variable=sms).grid(row=5, columnspan=2, sticky="w", pady=(10, 3))
    ttk.Label(frame, text=f"Allocation limit: {account.config['sms_max_allocations']}. Blank budget means no spending approved.").grid(row=6, columnspan=2, sticky="w")
    ttk.Checkbutton(frame, text="I approve the total SMS spending limit entered above", variable=approve).grid(row=7, columnspan=2, sticky="w", pady=4)
    ttk.Label(frame, text="Optional credentials — saved in your OS credential store. Blank preserves existing values.", wraplength=580).grid(row=8, columnspan=2, sticky="w", pady=(14, 6))
    secret_fields = {}
    for row, name in enumerate(credential_store.NAMES, 9):
        ttk.Label(frame, text=name).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        secret_fields[name] = tk.StringVar()
        ttk.Entry(frame, textvariable=secret_fields[name], show="*", width=46).grid(row=row, column=1, sticky="ew")
    replace = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text="Replace existing credentials for fields I filled in", variable=replace).grid(row=12, columnspan=2, sticky="w", pady=4)
    ttk.Label(frame, text="No Amazon password is collected. Saving creates no inbox, phone number, or schedule.", wraplength=580).grid(row=13, columnspan=2, sticky="w", pady=(10, 6))
    outcome = tk.StringVar(value="Settings prepared. Your agent must verify the live browser before reporting Day 1 ready.")
    ttk.Label(frame, textvariable=outcome, wraplength=580).grid(row=14, columnspan=2, sticky="w", pady=6)

    def save():
        credentials = {name: value.get() for name, value in secret_fields.items() if value.get()}
        try:
            settings = {name: field.get().strip() for name, field in fields.items()}
            settings["sms_max_total_usd"] = settings["sms_max_total_usd"] or None
            settings["sms_enabled"] = sms.get()
            save_settings(account, settings, credentials, approve.get(), replace.get())
            for field in secret_fields.values():
                field.set("")
            outcome.set("Configuration saved. Credentials entered were saved securely; provider connection not tested. Return to the agent and say 'configured'.")
            messagebox.showinfo("Saved", "Configuration saved. Return to the agent and say 'configured'.", parent=window)
        except WorkflowError as exc:
            messagebox.showerror("Setup needs attention", str(exc), parent=window)
        except Exception:
            messagebox.showerror("Setup needs attention", "Setup could not finish. No secret values were logged. Check the native credential store and saved configuration before retrying.", parent=window)
        finally:
            credentials.clear()

    buttons = ttk.Frame(frame)
    buttons.grid(row=15, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(buttons, text="Save settings and SMS limit", command=save).pack(side="left", padx=5)
    ttk.Button(buttons, text="Close / configure credentials later", command=window.destroy).pack(side="left", padx=5)
    window.mainloop()


def launch_setup(account):
    argv = [sys.executable, str(Path(__file__).resolve()), "--root", str(account.root), "open", account.account_id]
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    child = subprocess.Popen(argv, **kwargs)
    try:
        code = child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        return {"status": "setup_window_requested", "pid": child.pid, "instruction": "Save privately, then tell the agent 'configured'."}
    if code:
        raise WorkflowError("Setup window could not open; use the saved launcher or configure --prompt in your own terminal")
    return {"status": "setup_window_closed", "instruction": "Check setup status to see whether settings were saved."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Alternate accounts directory")
    parser.add_argument("command", choices=("prepare", "status", "open", "launch", "configure"))
    parser.add_argument("account_id", nargs="?", default="shopping-01")
    parser.add_argument("--marketplace")
    parser.add_argument("--timezone")
    parser.add_argument("--check-credentials", action="store_true", help="Check access; may trigger an OS unlock prompt. Outputs presence only.")
    parser.add_argument("--prompt", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            account, launcher = prepare(args.account_id, args.root, args.marketplace, args.timezone)
            result = report(account)
            result["setup_launcher"] = str(launcher)
        else:
            account = Account(args.account_id, args.root).load()
            if args.command == "open":
                gui_setup(account)
                return 0
            if args.command == "configure":
                if not args.prompt:
                    raise WorkflowError("Use configure --prompt in the user's interactive terminal")
                terminal_setup(account)
                return 0
            result = launch_setup(account) if args.command == "launch" else report(account, args.check_credentials)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except WorkflowError as exc:
        print(json.dumps({"status": "needs_setup", "reason": str(exc)}))
    except (KeyboardInterrupt, EOFError):
        print(json.dumps({"status": "cancelled"}))
    except Exception:
        print(json.dumps({"status": "needs_setup", "reason": "Local setup failed; inspect configuration and native storage without exposing credentials"}))
    return 2


if __name__ == "__main__":
    sys.exit(main())
