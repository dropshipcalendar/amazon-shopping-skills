"""Local state and guards for one two-day shopping workflow. No network calls."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class WorkflowError(Exception):
    pass


def data_directory(platform=None, environ=None, home=None):
    platform = platform or sys.platform
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    if platform == "win32":
        base = Path(environ.get("LOCALAPPDATA") or home / "AppData/Local")
    elif platform == "darwin":
        base = home / "Library/Application Support"
    else:
        base = Path(environ.get("XDG_DATA_HOME") or home / ".local/share")
    return base / "AmazonShoppingSkill"


def chrome_candidates(platform=None, environ=None, home=None):
    platform = platform or sys.platform
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    if platform == "win32":
        return [Path(environ[key]) / "Google/Chrome/Application/chrome.exe"
                for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA") if environ.get(key)]
    if platform == "darwin":
        return [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                home / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    return []


def environment_info():
    base = data_directory()
    executable = base / ("runtime/Scripts/python.exe" if sys.platform == "win32" else "runtime/bin/python")
    return {"platform": sys.platform, "data_directory": str(base),
            "accounts_directory": str(base / "accounts"), "runtime_python": str(executable),
            "runtime_exists": executable.is_file(),
            "chrome_candidates": [str(p) for p in chrome_candidates()]}


def write_browser_launcher(directory, argv, platform=None):
    platform = platform or sys.platform
    if platform == "win32":
        # Paths originate in the filesystem. Reject characters that could break
        # a batch line; quote every argument even when it contains no spaces.
        if any(any(c in value for c in ('"', '\n', '\r')) for value in argv):
            raise WorkflowError("Unsupported character in Windows launcher path")
        command = " ".join('"' + value.replace("%", "%%") + '"' for value in argv)
        shortcut = directory / "open-browser.cmd"
        shortcut.write_text('@echo off\nsetlocal DisableDelayedExpansion\nstart "" ' + command + "\n", encoding="utf-8")
    elif platform == "darwin":
        shortcut = directory / "open-browser.command"
        shortcut.write_text("#!/bin/sh\nexec " + shlex.join(argv) + "\n", encoding="utf-8")
        shortcut.chmod(0o700)
    else:
        raise WorkflowError("Browser launch supports Windows and macOS only")
    return shortcut


def now():
    return datetime.now(timezone.utc)


def stamp(value=None):
    return (value or now()).isoformat()


def money(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise WorkflowError("Invalid dollar amount") from None
    if not result.is_finite() or result < 0:
        raise WorkflowError("Dollar amount must be finite and nonnegative")
    return result


def write_json(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".state-", suffix=".tmp", delete=False) as f:
        temp = Path(f.name)
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def validate_config(config):
    config = dict(config)
    if "product_allowlist" not in config:
        allowlist_path = Path(__file__).resolve().parents[1] / "assets/product-allowlist.json"
        config["product_allowlist"] = json.loads(allowlist_path.read_text(encoding="utf-8"))
    defaults = dict(marketplace="https://www.amazon.com", timezone="America/Los_Angeles",
                    product_allowlist=[], browse_seconds=300, max_cart_additions=2,
                    email_domain="agentmail.to", sms_mode="verification", sms_max_total_usd=None,
                    sms_max_allocations=1)
    if set(config) - set(defaults):
        raise WorkflowError("Unknown configuration field")
    config = defaults | config
    try:
        ZoneInfo(config["timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        raise WorkflowError("Unknown timezone; install the pinned tzdata dependency") from None
    u = urlparse(config["marketplace"])
    # A marketplace is an origin, never a supplied redirect or arbitrary host.
    valid_host = re.fullmatch(r"(?:www\.)?amazon\.(?:com|ca|com\.mx|com\.br|co\.uk|de|fr|it|es|nl|se|pl|com\.be|ie|co\.jp|in|com\.au|sg|ae|sa|com\.tr|eg|co\.za)", u.hostname or "")
    if u.scheme != "https" or not valid_host or u.username or u.password or u.port or u.query or u.fragment or u.path not in ("", "/"):
        raise WorkflowError("Set marketplace to the HTTPS origin of the intended Amazon store")
    config["marketplace"] = config["marketplace"].rstrip("/")
    names = config["product_allowlist"]
    if not isinstance(names, list) or any(not isinstance(x, str) or not x.strip() or len(x) > 300 for x in names):
        raise WorkflowError("product_allowlist must be a list of nonempty product names")
    config["product_allowlist"] = list(dict.fromkeys(x.strip() for x in names))
    for key, low, high in (("browse_seconds", 1, 3600), ("max_cart_additions", 0, 20), ("sms_max_allocations", 1, 10)):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise WorkflowError(f"Invalid {key}")
    # Older configs used null while waiting for a mode choice. The user has now
    # chosen one-time verification; an unset spending cap still blocks purchases.
    if config["sms_mode"] is None:
        config["sms_mode"] = "verification"
    if config["sms_mode"] != "verification":
        raise WorkflowError("Only one-time SMS verification is supported; rentals are not allowed")
    if config["sms_max_total_usd"] is not None:
        if money(config["sms_max_total_usd"]) <= 0:
            raise WorkflowError("SMS spending cap must be positive")
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", config["email_domain"] or ""):
        raise WorkflowError("Invalid email domain")
    return config


class Account:
    def __init__(self, account_id, root=None):
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?", account_id):
            raise WorkflowError("Use a lowercase account ID containing only letters, digits, and hyphens")
        if account_id.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
            raise WorkflowError("Reserved Windows account ID")
        self.account_id = account_id
        self.root = Path(root or data_directory() / "accounts").resolve()
        self.path = self.root / account_id
        self.state_path = self.path / "state.json"
        self.config_path = self.path / "config.json"

    @contextmanager
    def locked(self, create=False):
        if create:
            self.path.mkdir(parents=True, exist_ok=True)
        if not self.path.is_dir():
            raise WorkflowError("Account is not initialized")
        lock = self.path / ".lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise WorkflowError("Account is busy; inspect the owner before recovering a stale .lock") from None
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield self
        finally:
            lock.unlink(missing_ok=True)

    def load(self):
        if not self.state_path.exists():
            raise WorkflowError("Account is not initialized")
        self.config = validate_config(json.loads(self.config_path.read_text(encoding="utf-8")))
        self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        if self.state.get("account_id") != self.account_id or self.state.get("version") != 1:
            raise WorkflowError("Unexpected state identity/version")
        # Backward-compatible: older version-1 accounts had no scheduler record.
        self.state.setdefault("schedule", None)
        return self

    def save(self):
        write_json(self.state_path, self.state)

    def initialize(self, config):
        if self.state_path.exists():
            return self.load().status()
        config = validate_config(config)
        self.config = config
        self.state = dict(version=1, account_id=self.account_id, created_at=stamp(), phase="new",
                          profile_verified_at=None, day_one_date=None, day_two_date=None,
                          elapsed_seconds=0, active_since=None, viewed=[], cart=[], inbox=None,
                          sms=[], completion=None, schedule=None)
        write_json(self.config_path, config)
        (self.path / "chrome-data").mkdir(exist_ok=True)
        self.save()
        return self.status()

    def elapsed(self):
        elapsed = self.state["elapsed_seconds"]
        if self.state["active_since"]:
            delta = (now() - datetime.fromisoformat(self.state["active_since"])).total_seconds()
            if delta < 0:
                raise WorkflowError("Clock moved backwards; reconcile browsing time")
            elapsed += delta
        return min(elapsed, self.config["browse_seconds"])

    def status(self):
        local_date = now().astimezone(ZoneInfo(self.config["timezone"])).date().isoformat()
        remaining = max(0, math.ceil(self.config["browse_seconds"] - self.elapsed()))
        due = self.state["day_two_date"]
        return dict(account_id=self.account_id, phase=self.state["phase"], local_date=local_date,
                    timezone=self.config["timezone"], day_two_date=due,
                    day_two_eligible=bool(due and local_date >= due and self.state["phase"] in ("waiting_day_two", "signup")),
                    remaining_seconds=remaining, timer_active=bool(self.state["active_since"]),
                    confirmed_cart_additions=sum(x["status"] == "confirmed" for x in self.state["cart"]),
                    uncertain_cart_actions=[x["id"] for x in self.state["cart"] if x["status"] == "intent"],
                    sms_reserved_usd=str(sum((money(x["reserved_usd"]) for x in self.state["sms"]), Decimal(0))),
                    schedule=self.state.get("schedule"),
                    schedule_cleanup_required=bool(self.state["phase"] == "complete" and self.state.get("schedule") and self.state["schedule"]["status"] != "removed"),
                    account_directory=str(self.path), config_path=str(self.config_path),
                    state_path=str(self.state_path), profile_path=str(self.path / "chrome-data/Default"))

    def verify_profile(self, observed):
        expected = (self.path / "chrome-data/Default").resolve()
        if Path(observed).resolve() != expected:
            raise WorkflowError("Observed profile does not match this account")
        self.state["profile_verified_at"] = stamp()
        self.save()
        return {"status": "profile_observation_recorded", "profile_path": str(expected)}

    def need_profile(self):
        if not self.state["profile_verified_at"]:
            raise WorkflowError("Observe and verify the actual Chrome profile first")

    def browse_start(self):
        self.need_profile()
        if self.state["phase"] not in ("new", "browsing"):
            raise WorkflowError("Browsing is already completed or signup has started")
        if not self.config["product_allowlist"]:
            raise WorkflowError("The configured allowlist is empty; remove the empty override to use the bundled list")
        if self.state["active_since"]:
            raise WorkflowError("Timer already active; resume that run or recover an interrupted timer")
        current = now()
        if not self.state["day_one_date"]:
            day = current.astimezone(ZoneInfo(self.config["timezone"])).date()
            self.state["day_one_date"] = day.isoformat()
            self.state["day_two_date"] = (day + timedelta(days=1)).isoformat()
        self.state.update(phase="browsing", active_since=stamp(current))
        self.save()
        return self.status()

    def browse_stop(self, result, recovered_seconds=None):
        if self.state["phase"] != "browsing" or not self.state["active_since"]:
            raise WorkflowError("No active browsing timer")
        if recovered_seconds is not None:
            if not math.isfinite(recovered_seconds) or recovered_seconds < 0 or recovered_seconds > self.elapsed() - self.state["elapsed_seconds"] + 0.01:
                raise WorkflowError("Recovered time exceeds the elapsed interval")
            elapsed = self.state["elapsed_seconds"] + recovered_seconds
        else:
            elapsed = self.elapsed()
        if result == "completed" and (elapsed < self.config["browse_seconds"] or not self.state["viewed"]):
            raise WorkflowError("Complete the browsing duration and record actual viewed products first")
        self.state.update(elapsed_seconds=elapsed, active_since=None, last_browse_result=result)
        if result == "completed":
            self.state["phase"] = "waiting_day_two"
        self.save()
        return self.status()

    def product(self, name, url):
        if self.state["phase"] != "browsing" or not self.state["active_since"] or self.elapsed() >= self.config["browse_seconds"]:
            raise WorkflowError("No active browsing time remains")
        allowed = {x.casefold(): x for x in self.config["product_allowlist"]}
        if name.casefold() not in allowed:
            raise WorkflowError("Product is not in the configured allowlist")
        u, store = urlparse(url), urlparse(self.config["marketplace"])
        if u.scheme != "https" or u.hostname not in (store.hostname, store.hostname.removeprefix("www.")) or u.username or u.password or u.port:
            raise WorkflowError("Product URL must belong to the configured Amazon marketplace")
        return allowed[name.casefold()]

    def viewed(self, name, url):
        product = self.product(name, url)
        self.state["viewed"] = (self.state["viewed"] + [dict(product=product, url=url, at=stamp())])[-100:]
        self.save()
        return {"status": "view_recorded"}

    def cart_intent(self, name, url):
        product = self.product(name, url)
        pending = [x for x in self.state["cart"] if x["status"] != "not_added"]
        if any(x["product"].casefold() == product.casefold() or x["url"] == url for x in pending):
            raise WorkflowError("Product already added or has an unresolved cart intent")
        if len(pending) >= self.config["max_cart_additions"]:
            raise WorkflowError("Cart addition limit reached")
        action = dict(id=uuid.uuid4().hex, product=product, url=url, quantity=1, status="intent", at=stamp())
        self.state["cart"].append(action)
        self.save()
        return action

    def cart_result(self, action_id, status):
        action = next((x for x in self.state["cart"] if x["id"] == action_id), None)
        if not action or action["status"] not in ("intent", status):
            raise WorkflowError("No matching unresolved cart intent")
        action["status"] = status
        self.save()
        return {"id": action_id, "status": status}

    def signup_start(self):
        self.need_profile()
        if self.state["phase"] == "signup":
            return self.status()
        if not self.status()["day_two_eligible"]:
            raise WorkflowError("Signup requires completed Day 1 and its next calendar date")
        if any(x["status"] == "intent" for x in self.state["cart"]):
            raise WorkflowError("Reconcile unresolved Day 1 cart actions first")
        self.state["phase"] = "signup"
        self.save()
        return self.status()

    def need_signup(self):
        if self.state["phase"] != "signup":
            raise WorkflowError("This action is available only during Day 2 signup")

    def reserve_sms(self, amount, service, kind):
        self.need_signup()
        if kind != "verification":
            raise WorkflowError("Only one-time SMS verification allocations are allowed")
        if self.config["sms_mode"] != kind or self.config["sms_max_total_usd"] is None:
            raise WorkflowError("Explicit SMS mode and spending authorization are required")
        records = self.state["sms"]
        if any(x["status"] in ("pending", "uncertain", "allocated") for x in records):
            raise WorkflowError("Reuse or reconcile the existing SMS allocation; do not buy another")
        if len(records) >= self.config["sms_max_allocations"]:
            raise WorkflowError("SMS allocation attempt limit reached")
        cost = money(amount)
        total = sum((money(x["reserved_usd"]) for x in records), Decimal(0))
        if total + cost > money(self.config["sms_max_total_usd"]):
            raise WorkflowError("SMS quote exceeds remaining authorized budget")
        item = dict(id=uuid.uuid4().hex, service=service, kind=kind, reserved_usd=str(cost),
                    status="pending", requested_at=stamp(), provider_id=None)
        records.append(item)
        self.save()
        return item

    def sms_result(self, entry_id, status, provider_id=None):
        item = next((x for x in self.state["sms"] if x["id"] == entry_id), None)
        if not item:
            raise WorkflowError("SMS ledger entry not found")
        if status == "allocated" and not (provider_id or item["provider_id"]):
            raise WorkflowError("Allocation requires the observed provider ID")
        item.update(status=status, provider_id=provider_id or item["provider_id"])
        self.save()
        return item

    def complete(self, evidence):
        self.need_signup()
        if not evidence.strip() or not self.state["inbox"]:
            raise WorkflowError("Record the assigned inbox and observed signup confirmation first")
        if any(x["status"] in ("pending", "uncertain") for x in self.state["sms"]):
            raise WorkflowError("Reconcile the uncertain SMS purchase first")
        self.state.update(phase="complete", completion=dict(at=stamp(), evidence=evidence[:500]))
        schedule = self.state.get("schedule")
        if schedule and schedule["status"] != "removed" and schedule.get("automation_id"):
            schedule.update(status="removal_pending", pending_action="remove", updated_at=stamp())
        self.save()
        return self.status()

    def schedule_prepare(self, thread_id, local_time):
        """Reserve one same-chat schedule intent. This never contacts a scheduler."""
        if self.state["phase"] == "complete":
            raise WorkflowError("Completed workflows must clean up schedules, not create one")
        if not thread_id.strip():
            raise WorkflowError("The actual current chat ID is required")
        if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", local_time):
            raise WorkflowError("Use a local 24-hour time in HH:MM format")
        existing = self.state.get("schedule")
        if existing:
            if existing["thread_id"] != thread_id or existing["local_time"] != local_time or existing["timezone"] != self.config["timezone"]:
                raise WorkflowError("A schedule record already exists; inspect and update that automation instead of creating another")
            return existing
        zone = ZoneInfo(self.config["timezone"])
        first_date = self.state.get("day_two_date") or (now().astimezone(zone).date() + timedelta(days=1)).isoformat()
        target = datetime.fromisoformat(first_date + "T" + local_time).replace(tzinfo=zone, fold=0)
        if target.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != target.replace(tzinfo=None):
            raise WorkflowError("Selected local time does not exist on that date; choose another time")
        # A late manual resume can target today, but never authorizes a second schedule.
        schedule = dict(intent_id=uuid.uuid4().hex, automation_id=None, thread_id=thread_id,
                        local_time=local_time, timezone=self.config["timezone"], first_run_at=target.isoformat(),
                        status="create_pending", pending_action="create", created_at=stamp(), updated_at=stamp())
        self.state["schedule"] = schedule
        self.save()
        return schedule

    def schedule_record(self, intent_id, automation_id):
        schedule = self.state.get("schedule")
        if not schedule or schedule["intent_id"] != intent_id or not automation_id.strip():
            raise WorkflowError("Matching schedule intent and actual returned automation ID are required")
        if schedule["automation_id"]:
            if schedule["automation_id"] != automation_id:
                raise WorkflowError("Never overwrite the existing automation ID with another schedule")
            return schedule
        if schedule["status"] not in ("create_pending", "uncertain") or schedule["pending_action"] != "create":
            raise WorkflowError("No unresolved schedule creation to record")
        cleanup = self.state["phase"] == "complete"
        schedule.update(automation_id=automation_id, status="removal_pending" if cleanup else "active",
                        pending_action="remove" if cleanup else None, updated_at=stamp())
        self.save()
        return schedule

    def schedule_action(self, action, automation_id):
        schedule = self.state.get("schedule")
        if not schedule or not automation_id or schedule["automation_id"] != automation_id:
            raise WorkflowError("Use only this account's recorded automation ID")
        if action not in ("pause", "resume", "remove"):
            raise WorkflowError("Unsupported scheduler action")
        if self.state["phase"] == "complete" and action != "remove":
            raise WorkflowError("Only schedule removal is allowed after workflow completion")
        if schedule["status"] == "removed":
            if action == "remove": return schedule
            raise WorkflowError("A removed schedule cannot be resumed or paused")
        if schedule["pending_action"] and schedule["pending_action"] != action:
            raise WorkflowError("Reconcile the pending scheduler action before another action")
        if (schedule["status"], action) in (("paused", "pause"), ("active", "resume")):
            return schedule
        schedule.update(status={"pause": "pause_pending", "resume": "resume_pending", "remove": "removal_pending"}[action],
                        pending_action=action, updated_at=stamp())
        self.save()
        return schedule

    def schedule_result(self, action, automation_id, outcome):
        schedule = self.state.get("schedule")
        if not schedule or not automation_id or schedule["automation_id"] != automation_id:
            raise WorkflowError("Scheduler result must match this account's automation ID")
        expected = {"pause": "paused", "resume": "active", "remove": "removed"}.get(action)
        if expected is None or outcome not in ("confirmed", "uncertain"):
            raise WorkflowError("Invalid scheduler result")
        if schedule["pending_action"] is None and schedule["status"] == expected and outcome == "confirmed":
            return schedule
        if schedule["pending_action"] != action:
            raise WorkflowError("Result does not match the pending scheduler action")
        schedule.update(status=expected if outcome == "confirmed" else "uncertain",
                        pending_action=None if outcome == "confirmed" else action, updated_at=stamp())
        self.save()
        return schedule

    def schedule_creation_result(self, intent_id, outcome):
        schedule = self.state.get("schedule")
        if not schedule or schedule["intent_id"] != intent_id or schedule["automation_id"]:
            raise WorkflowError("No matching unresolved schedule creation")
        if schedule["pending_action"] != "create" or outcome not in ("uncertain", "confirmed_absent"):
            raise WorkflowError("Invalid schedule creation reconciliation")
        if outcome == "confirmed_absent" and self.state["phase"] == "complete":
            schedule.update(status="removed", pending_action=None)
        else:
            schedule.update(status="uncertain" if outcome == "uncertain" else "create_pending", pending_action="create")
        schedule["updated_at"] = stamp()
        self.save()
        return schedule

    def profile(self):
        return {"user_data_directory": str(self.path / "chrome-data"),
                "expected_profile_path": str(self.path / "chrome-data/Default"),
                "arguments": ["--user-data-dir=" + str(self.path / "chrome-data"), "--no-first-run", "chrome://version"]}

    def launch(self):
        if sys.platform not in ("win32", "darwin"):
            raise WorkflowError("Browser launch supports Windows and macOS only")
        candidates = chrome_candidates()
        chrome = next((p for p in candidates if p.is_file()), None)
        if not chrome:
            raise WorkflowError("Chrome executable not found in standard installation paths; inspect environment output")
        info = self.profile()
        (self.path / "chrome-data").mkdir(exist_ok=True)
        argv = [str(chrome), *info["arguments"]]
        shortcut = write_browser_launcher(self.path, argv)
        # Invalidate old UI proof before launching, including an uncertain launch.
        self.state["profile_verified_at"] = None
        self.save()
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return info | {"shortcut": str(shortcut), "status": "launched_verify_actual_profile"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", help="Alternate runtime root; normally omit")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("environment", help="Report OS and nonsecret runtime/browser paths without changing anything")
    for name in ("init", "status", "profile", "launch", "verify-profile", "browse-start", "browse-stop", "browse-recover", "viewed", "cart-intent", "cart-confirm", "cart-not-added", "signup-start", "signup-complete", "reserve-sms", "sms-result", "schedule-prepare", "schedule-record", "schedule-action", "schedule-result", "schedule-creation-result"):
        q = sub.add_parser(name)
        q.add_argument("account_id")
        if name == "init": q.add_argument("--config", required=True)
        if name == "verify-profile": q.add_argument("--observed-path", required=True)
        if name == "browse-stop": q.add_argument("--result", required=True, choices=("completed", "interrupted", "blocked"))
        if name == "browse-recover": q.add_argument("--observed-seconds", required=True, type=float)
        if name in ("viewed", "cart-intent"):
            q.add_argument("--product", required=True); q.add_argument("--url", required=True)
        if name in ("cart-confirm", "cart-not-added"): q.add_argument("--action-id", required=True)
        if name == "signup-complete": q.add_argument("--evidence", required=True)
        if name == "reserve-sms":
            q.add_argument("--amount", required=True); q.add_argument("--service", required=True)
            q.add_argument("--kind", default="verification", choices=("verification",))
        if name == "sms-result":
            q.add_argument("--entry-id", required=True); q.add_argument("--provider-id")
            q.add_argument("--status", required=True, choices=("allocated", "uncertain", "cancelled", "completed", "failed"))
        if name == "schedule-prepare":
            q.add_argument("--thread-id", required=True); q.add_argument("--local-time", required=True)
        if name in ("schedule-record", "schedule-creation-result"):
            q.add_argument("--intent-id", required=True)
        if name in ("schedule-record", "schedule-action", "schedule-result"):
            q.add_argument("--automation-id", required=True)
        if name in ("schedule-action", "schedule-result"):
            q.add_argument("--action", required=True, choices=("pause", "resume", "remove"))
        if name == "schedule-result":
            q.add_argument("--outcome", required=True, choices=("confirmed", "uncertain"))
        if name == "schedule-creation-result":
            q.add_argument("--outcome", required=True, choices=("uncertain", "confirmed_absent"))
    args = p.parse_args()
    try:
        if args.command == "environment":
            print(json.dumps(environment_info(), ensure_ascii=False))
            return 0
        account = Account(args.account_id, args.root)
        with account.locked(create=args.command == "init"):
            if args.command == "init":
                result = account.initialize(json.loads(Path(args.config).read_text(encoding="utf-8-sig")))
            else:
                account.load()
                name = args.command
                if name in ("status", "profile", "launch", "browse-start", "signup-start"):
                    result = getattr(account, name.replace("-", "_"))()
                elif name == "verify-profile": result = account.verify_profile(args.observed_path)
                elif name == "browse-stop": result = account.browse_stop(args.result)
                elif name == "browse-recover": result = account.browse_stop("interrupted", args.observed_seconds)
                elif name in ("viewed", "cart-intent"): result = getattr(account, name.replace("-", "_"))(args.product, args.url)
                elif name.startswith("cart-"): result = account.cart_result(args.action_id, "confirmed" if name == "cart-confirm" else "not_added")
                elif name == "signup-complete": result = account.complete(args.evidence)
                elif name == "reserve-sms": result = account.reserve_sms(args.amount, args.service, args.kind)
                elif name == "sms-result": result = account.sms_result(args.entry_id, args.status, args.provider_id)
                elif name == "schedule-prepare": result = account.schedule_prepare(args.thread_id, args.local_time)
                elif name == "schedule-record": result = account.schedule_record(args.intent_id, args.automation_id)
                elif name == "schedule-action": result = account.schedule_action(args.action, args.automation_id)
                elif name == "schedule-result": result = account.schedule_result(args.action, args.automation_id, args.outcome)
                elif name == "schedule-creation-result": result = account.schedule_creation_result(args.intent_id, args.outcome)
            print(json.dumps(result, ensure_ascii=False))
    except WorkflowError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)})); return 2
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"status": "blocked", "reason": "Local configuration/state error; inspect files without exposing secrets"})); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
