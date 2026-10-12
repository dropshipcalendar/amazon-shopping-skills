"""Initial provider setup. No Amazon actions, SMS purchases, or schedules.

Commands return status and nonsecret identifiers only. Signup requires its own
explicit flag; lost/uncertain provisioning results never trigger another signup.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import uuid
from urllib.parse import quote

from workflow import Account, WorkflowError, stamp, write_json
from secure_store import CredentialStore, FIELDS, migrate_legacy, resolve, validate_record
from providers import agentmail_request, email_create, phone_readiness, textverified_client


@contextmanager
def connection_lock(account):
    directory = account.root / ".connections"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = directory / ".lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise WorkflowError("Provider setup is busy; inspect its owner before resuming") from None
    try:
        os.close(descriptor)
        yield directory
    finally:
        lock.unlink(missing_ok=True)


def status(account, store):
    connections = {}
    for provider in FIELDS:
        if provider == "textverified" and not account.config["sms_enabled"]:
            connections[provider] = {"disabled": True}
            continue
        record = resolve(provider, store)
        connections[provider] = {"configured": record is not None}
    return {"connections": connections, "checks": account.state.get("setup", {})}


def bind_bootstrap(account, record):
    inbox = record.get("bootstrap_inbox")
    if not inbox:
        return
    if record.get("bootstrap_owner") != str(account.path):
        raise WorkflowError("This bootstrap inbox belongs to another workflow; connect an authorized AgentMail account")
    if account.state["inbox"] and account.state["inbox"] != inbox:
        raise WorkflowError("Existing inbox assignment differs; reconcile it before proceeding")
    account.state["inbox"] = inbox
    account.save()


def email_connect(account, store, directory, allow_signup=False, request=None, environ=None):
    account.need_setup()
    request = request or agentmail_request
    record = resolve("agentmail", store, environ)
    intent_path = directory / "agentmail-signup.json"
    if record is None:
        if account.state["inbox"]:
            raise WorkflowError("Assigned inbox has no credential; reconnect it instead of creating another")
        if intent_path.exists():
            raise WorkflowError("Prior AgentMail signup is unresolved; recover its credential before any retry")
        if not allow_signup:
            raise WorkflowError("AgentMail access missing; initial signup requires authorized --allow-signup")
        store.probe()
        intent = {"owner": str(account.path), "status": "pending", "at": stamp(),
                  "username": "shopping-" + uuid.uuid4().hex[:20]}
        write_json(intent_path, intent)
        # This request is deliberately not retried, even after an HTTP error:
        # without a human email, another request may create another organization.
        try:
            response = request("POST", "agent/sign-up", {"username": intent["username"]}, anonymous=True)
            record = validate_record("agentmail", {"api_key": response["api_key"]})
            inbox_id, organization_id = response["inbox_id"], response["organization_id"]
            if not isinstance(inbox_id, str) or "@" not in inbox_id or not isinstance(organization_id, str) or not organization_id:
                raise ValueError
            record.update(organization_id=organization_id, bootstrap_owner=str(account.path),
                          bootstrap_inbox={"inbox_id": inbox_id, "email": inbox_id})
            # Persist the key and binding in one vault item before public state.
            store.write("agentmail", record)
        except Exception:
            intent["status"] = "uncertain"
            write_json(intent_path, intent)
            raise WorkflowError("AgentMail signup/save is unresolved; do not repeat signup") from None
    bind_bootstrap(account, record)
    def authenticated(method, route, payload=None):
        return request(method, route, payload, credential=record)
    if not account.state["inbox"]:
        # Existing provider connection: create exactly one assigned inbox using
        # the existing durable client ID. No new provider organization.
        authenticated("GET", "inboxes?limit=1")
        email_create(account, authenticated, setup=True)
    inbox_id = account.state["inbox"]["inbox_id"]
    observed = authenticated("GET", "inboxes/" + quote(inbox_id, safe=""))
    if observed.get("inbox_id") != inbox_id:
        raise WorkflowError("AgentMail returned a different inbox; reconcile the assignment")
    account.state.setdefault("setup", {})["email"] = {"status": "ready", "checked_at": stamp()}
    account.save()
    if intent_path.exists() and record.get("bootstrap_owner") == str(account.path):
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
        intent["status"] = "saved"
        write_json(intent_path, intent)
    return {"status": "ready", "provider": "agentmail"}


def check_textverified(record, client_factory=None):
    client = (client_factory or textverified_client)(record)
    try:
        details = client.account.me()
        if details.username.casefold() != record["username"].casefold():
            raise WorkflowError("TextVerified account differs from the selected login")
    finally:
        client.session.close()


def save_record(provider, record, store, replace=False, client_factory=None):
    validate_record(provider, record)
    existing = store.read(provider)
    if existing:
        matches = all(existing[field] == record[field] for field in FIELDS[provider])
        if matches:
            return {"status": "saved", "provider": provider}
        if not replace:
            raise WorkflowError("A different credential is saved; explicit reconnection is required")
    if provider == "textverified":
        check_textverified(record, client_factory)
    store.write(provider, record)
    return {"status": "saved", "provider": provider}


def save_environment(provider, store, replace=False, environ=None, client_factory=None):
    environ = os.environ if environ is None else environ
    record = {field: environ.get(name) for field, name in FIELDS[provider].items()}
    return save_record(provider, record, store, replace, client_factory)


def capture_textverified(username, store, replace=False, clipboard=None, client_factory=None):
    # Call only immediately after the agent/user selected the intended key's
    # Copy button. No general clipboard search or secret output.
    if clipboard is None:
        import pyperclip as clipboard
    value = clipboard.paste()
    try:
        record = {"api_key": value, "username": username}
        return save_record("textverified", record, store, replace, client_factory)
    finally:
        # Clear only the captured key, never a newer unrelated clipboard value.
        if clipboard.paste() == value:
            clipboard.copy("")


def begin_signup(account, store, directory, service, request=None, client_factory=None):
    """Gate initial Day 2 entry on live access/balance, not yesterday's status."""
    account.need_profile()
    if account.state["phase"] == "signup":
        return account.status()
    if not account.status()["day_two_eligible"]:
        raise WorkflowError("Signup requires completed Day 1 and its next calendar date")
    if any(x["status"] == "intent" for x in account.state["cart"]):
        raise WorkflowError("Reconcile unresolved Day 1 cart actions first")
    email_connect(account, store, directory, request=request)
    if not account.config["sms_enabled"]:
        return account.signup_start()
    record = resolve("textverified", store)
    if record is None:
        raise WorkflowError("TextVerified access missing; reconnect it before registration")
    client = (client_factory or textverified_client)(record)
    try:
        check = phone_readiness(account, client, service)
    finally:
        client.session.close()
    if not check["ready"]:
        raise WorkflowError("SMS readiness check failed; inspect balance, spending cap, and allocation limit")
    return account.signup_start()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root")
    parser.add_argument("command", choices=("prepare", "status", "migrate-credentials", "email-connect", "save-environment", "capture-textverified", "signup-start"))
    parser.add_argument("account_id", nargs="?", default="shopping-01")
    parser.add_argument("--allow-signup", action="store_true")
    parser.add_argument("--provider", choices=tuple(FIELDS))
    parser.add_argument("--account-email")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--service")
    parser.add_argument("--timezone")
    parser.add_argument("--marketplace")
    args = parser.parse_args()
    if args.command == "save-environment" and not args.provider:
        parser.error("--provider is required")
    if args.command == "capture-textverified" and not args.account_email:
        parser.error("--account-email is required")
    try:
        account, store = Account(args.account_id, args.root), CredentialStore()
        with account.locked(create=args.command == "prepare"):
            if args.command == "prepare":
                if not account.state_path.exists():
                    if args.timezone:
                        timezone = args.timezone
                    else:
                        from tzlocal import get_localzone_name
                        timezone = get_localzone_name()
                    config = {"timezone": timezone}
                    if args.marketplace:
                        config["marketplace"] = args.marketplace
                    account.initialize(config)
                else:
                    account.load()
                print(json.dumps(account.status()))
                return 0
            account.load()
            if args.command == "status":
                result = status(account, store)
            else:
                account.need_setup()
                with connection_lock(account) as directory:
                    if args.command == "migrate-credentials":
                        result = migrate_legacy(account, store)
                    elif args.command == "email-connect":
                        result = email_connect(account, store, directory, args.allow_signup)
                    elif args.command == "save-environment":
                        result = save_environment(args.provider, store, args.replace)
                    elif args.command == "signup-start":
                        if account.config["sms_enabled"] and not args.service:
                            raise WorkflowError("Select the current Amazon SMS service before registration")
                        result = begin_signup(account, store, directory, args.service)
                    else:
                        result = capture_textverified(args.account_email, store, args.replace)
            print(json.dumps(result))
    except WorkflowError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    except ImportError:
        print(json.dumps({"status": "blocked", "reason": "Install scripts/requirements.txt in the private runtime"}))
        return 2
    except Exception:
        # SDK, vault and clipboard exceptions can embed the captured value.
        print(json.dumps({"status": "blocked", "reason": "Provider setup unavailable; preserve saved access and inspect the connection"}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
