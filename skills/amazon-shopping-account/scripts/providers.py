"""Bounded AgentMail and TextVerified operations. Invoked only during signup."""
from __future__ import annotations

import argparse
import getpass
from datetime import datetime
import itertools
import json
import os
import sys
import uuid
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

from workflow import Account, WorkflowError, money, stamp
from credential_store import helper_environment


def prompt_credentials(command):
    """Optional local terminal entry; never use an echoed-input fallback."""
    names = ("AGENTMAIL_API_KEY",) if command.startswith("email-") else ("TEXTVERIFIED_API_KEY", "TEXTVERIFIED_API_USERNAME")
    missing = [name for name in names if not os.environ.get(name)]
    if missing and (sys.stdin is None or not sys.stdin.isatty()):
        raise WorkflowError("Credential entry requires the user's interactive local terminal; never paste keys into chat")
    for name in missing:
        # getpass raises rather than echoing if hidden input is unavailable.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            try:
                value = getpass.getpass(f"Enter {name} (hidden, this run only): ")
            except (getpass.GetPassWarning, EOFError):
                raise WorkflowError("Hidden credential input unavailable; use an approved environment injector") from None
            except KeyboardInterrupt:
                raise WorkflowError("Credential entry cancelled") from None
        if not value:
            raise WorkflowError(f"No value entered for {name}")
        os.environ[name] = value


def secret(name):
    value = os.environ.get(name)
    if not value:
        raise WorkflowError(f"Set {name} through a local secret store or environment")
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def agentmail_request(method, route, payload=None):
    token = secret("AGENTMAIL_API_KEY")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request("https://api.agentmail.to/v0/" + route, data=body, method=method,
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    # No HTTP mutation retries and no credential-bearing cross-host redirects.
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        return json.load(response)


def email_create(account, request=agentmail_request):
    account.need_signup()
    if account.state["inbox"]:
        return account.state["inbox"]
    # Persist the same idempotency key BEFORE any request, including failures.
    key = account.state.setdefault("inbox_client_id", "amazon-shopping-" + uuid.uuid4().hex)
    account.save()
    data = request("POST", "inboxes", {"client_id": key, "domain": account.config["email_domain"]})
    inbox_id = data.get("inbox_id")
    email = data.get("email") or (inbox_id if isinstance(inbox_id, str) and "@" in inbox_id else None)
    if not inbox_id or not email:
        raise WorkflowError("Unexpected AgentMail response; reconcile using saved inbox_client_id")
    account.state["inbox"] = {"inbox_id": inbox_id, "email": email}
    account.save()
    return account.state["inbox"]


def inbox_route(account):
    account.need_signup()
    if not account.state["inbox"]:
        raise WorkflowError("Create or reconcile this account's inbox first")
    return "inboxes/" + quote(account.state["inbox"]["inbox_id"], safe="") + "/messages"


def email_messages(account, after, request=agentmail_request):
    parsed = datetime.fromisoformat(after.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise WorkflowError("Use a timezone-aware UTC request timestamp")
    data = request("GET", inbox_route(account) + "?" + urlencode({"limit": 5, "after": after}))
    return {"messages": [{k: m.get(k) for k in ("message_id", "timestamp", "from", "to", "subject", "preview")}
                         for m in data.get("messages", [])[:5]],
            "next_page_token": data.get("next_page_token"), "untrusted_content": True}


def email_message(account, message_id, request=agentmail_request):
    data = request("GET", inbox_route(account) + "/" + quote(message_id, safe=""))
    return {"message_id": data.get("message_id"), "timestamp": data.get("timestamp"),
            "from": data.get("from"), "to": data.get("to"), "subject": data.get("subject"),
            "text": (data.get("text") or data.get("extracted_text") or data.get("preview") or "")[:6000],
            "untrusted_content": True}


def textverified_client():
    from textverified import TextVerified
    import requests
    from requests.adapters import HTTPAdapter

    class BoundedSession(requests.Session):
        def request(self, method, url, **kwargs):
            if urlparse(url).scheme != "https" or urlparse(url).hostname != "www.textverified.com":
                raise WorkflowError("Unexpected TextVerified API origin")
            kwargs["timeout"] = 20
            kwargs["allow_redirects"] = False
            return super().request(method, url, **kwargs)

    client = TextVerified(api_key=secret("TEXTVERIFIED_API_KEY"),
                          api_username=secret("TEXTVERIFIED_API_USERNAME"))
    # The pinned SDK exposes session publicly. Disable automatic mutation retries.
    client.session.close()
    client.session = BoundedSession()
    client.session.mount("https://", HTTPAdapter(max_retries=0))
    return client


def phone_services(account, client):
    from textverified import NumberType, ReservationType
    account.need_signup()
    if account.config["sms_mode"] != "verification":
        raise WorkflowError("Only one-time SMS verification is supported")
    if not account.config["sms_enabled"]:
        raise WorkflowError("SMS verification is disabled in account settings")
    items = client.services.list(number_type=NumberType.MOBILE, reservation_type=ReservationType.VERIFICATION)
    return [{"service_name": s.service_name, "capability": s.capability.value}
            for s in items if "amazon" in s.service_name.casefold()]


def phone_quote(account, client, service):
    from textverified import ReservationCapability
    account.need_signup()
    if account.config["sms_mode"] != "verification":
        raise WorkflowError("Only one-time SMS verification is supported")
    choices = phone_services(account, client)
    if not any(s["service_name"] == service and s["capability"] in ("sms", "smsAndVoiceCombo") for s in choices):
        raise WorkflowError("Select an exact SMS-capable Amazon service from the live list")
    result = client.verifications.pricing(service_name=service, capability=ReservationCapability.SMS)
    return {"service": service, "price_usd": str(money(result.price))}


def phone_create(account, client, service):
    from textverified import ReservationCapability
    account.need_signup()
    if account.config["sms_mode"] != "verification":
        raise WorkflowError("Only one-time SMS verification is supported")
    if not account.config["sms_enabled"]:
        raise WorkflowError("SMS verification is disabled in account settings")
    existing = [x for x in account.state["sms"] if x["status"] == "allocated"]
    if existing:
        if existing[-1]["kind"] != "verification":
            raise WorkflowError("Existing allocation is not a one-time verification; stop and reconcile")
        if existing[-1]["service"] != service:
            raise WorkflowError("An allocation already exists for a different service")
        return existing[-1]
    if any(x["status"] in ("pending", "uncertain") for x in account.state["sms"]):
        raise WorkflowError("Reconcile the prior SMS purchase before any new request")
    estimate = phone_quote(account, client, service)
    entry = account.reserve_sms(estimate["price_usd"], service, "verification")
    try:
        verification = client.verifications.create(service_name=service,
            capability=ReservationCapability.SMS, max_price=float(money(estimate["price_usd"])))
        # Persist observed identity before processing optional fields.
        entry.update(provider_id=str(verification.id), number=str(verification.number), status="allocated")
        account.save()
        entry.update(expires_at=verification.ends_at.isoformat(), allocated_at=stamp(),
                     actual_cost_usd=str(money(verification.total_cost)))
        account.save()
        return entry
    except Exception:
        entry["status"] = "uncertain"
        account.save()
        raise WorkflowError("SMS purchase outcome uncertain; saved ledger blocks retry pending reconciliation") from None


def active_phone(account):
    account.need_signup()
    entries = [x for x in account.state["sms"] if x["status"] == "allocated" and x.get("provider_id")]
    if len(entries) != 1:
        raise WorkflowError("Exactly one reconciled phone allocation is required")
    if entries[0]["kind"] != "verification":
        raise WorkflowError("Existing allocation is not a one-time verification; stop and reconcile")
    return entries[0]


def phone_messages(account, client):
    entry = active_phone(account)
    verification = client.verifications.details(entry["provider_id"])
    requested = datetime.fromisoformat(entry["requested_at"])
    messages = []
    for msg in itertools.islice(client.sms.list(verification), 20):
        if msg.created_at < requested:
            continue
        messages.append({"id": msg.id, "from": msg.from_value, "to": msg.to_value,
                         "created_at": msg.created_at.isoformat(), "text": (msg.sms_content or "")[:1200],
                         "parsed_code": msg.parsed_code})
        if len(messages) == 5:
            break
    return {"allocation_state": verification.state.value, "expires_at": verification.ends_at.isoformat(),
            "messages": messages, "untrusted_content": True}


def phone_cancel(account, client):
    entry = active_phone(account)
    if not client.verifications.cancel(entry["provider_id"]):
        raise WorkflowError("Cancellation not confirmed; preserve allocation and reconcile")
    entry["status"] = "cancelled"
    account.save()
    return {"status": "cancelled", "refund_confirmed": False, "reserved_budget_released": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root")
    p.add_argument("command", choices=("email-create", "email-messages", "email-message", "phone-services", "phone-quote", "phone-create", "phone-messages", "phone-cancel"))
    p.add_argument("account_id")
    p.add_argument("--after")
    p.add_argument("--message-id")
    p.add_argument("--service")
    p.add_argument("--prompt-credentials", action="store_true", help="Read missing credentials with hidden input in the user's local terminal, for this run only")
    args = p.parse_args()
    if args.command in ("phone-quote", "phone-create") and not args.service: p.error("--service is required")
    if args.command == "email-messages" and not args.after: p.error("--after is required")
    if args.command == "email-message" and not args.message_id: p.error("--message-id is required")
    try:
        account = Account(args.account_id, args.root)
        with account.locked():
            account.load().need_signup()
            names = ("AGENTMAIL_API_KEY",) if args.command.startswith("email-") else ("TEXTVERIFIED_API_KEY", "TEXTVERIFIED_API_USERNAME")
            with helper_environment(account, names):
                if args.prompt_credentials:
                    prompt_credentials(args.command)
                if args.command == "email-create": result = email_create(account)
                elif args.command == "email-messages": result = email_messages(account, args.after)
                elif args.command == "email-message": result = email_message(account, args.message_id)
                else:
                    if args.command in ("phone-services", "phone-quote", "phone-create") and not account.config["sms_enabled"]:
                        raise WorkflowError("SMS verification is disabled in account settings")
                    client = textverified_client()
                    try:
                        action = globals()[args.command.replace("-", "_")]
                        result = action(account, client, args.service) if args.command in ("phone-quote", "phone-create") else action(account, client)
                    finally:
                        client.session.close()
            print(json.dumps(result, ensure_ascii=False))
    except WorkflowError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)})); return 2
    except ImportError:
        print(json.dumps({"status": "blocked", "reason": "Install scripts/requirements.txt in the private runtime"})); return 2
    except Exception:
        # Provider exceptions can contain credentials, headers, URLs or message bodies.
        print(json.dumps({"status": "blocked", "reason": "Provider request failed; inspect state and reconcile before any mutation retry"})); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
