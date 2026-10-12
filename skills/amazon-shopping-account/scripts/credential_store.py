"""Compatibility access for credentials saved by earlier skill versions."""
from __future__ import annotations

import hashlib

from workflow import WorkflowError

NAMES = ("AGENTMAIL_API_KEY", "TEXTVERIFIED_API_KEY", "TEXTVERIFIED_API_USERNAME")


class StoreError(WorkflowError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Native credential store {status}; unlock it or use approved environment injection")


def backend():
    try:
        from secure_store import native_backend
        return native_backend()
    except StoreError:
        raise
    except Exception:
        raise StoreError("unavailable") from None


def service(account):
    # Separate accounts and alternate data roots; no credentials in identifiers.
    digest = hashlib.sha256(str(account.path).encode()).hexdigest()[:24]
    return f"AmazonShoppingSkill/{account.account_id}/{digest}"


def validate_name(name):
    if name not in NAMES:
        raise WorkflowError("Unknown credential name")


def store_call(operation, *args):
    try:
        return operation(*args)
    except Exception as exc:
        # Backend exception text can contain the value or private diagnostics.
        status = "locked" if type(exc).__name__ == "KeyringLocked" else "unavailable"
        raise StoreError(status) from None


def harden_windows(account):
    """Explicitly migrate this account's saved values; never inspect the whole vault."""
    from windows_credentials import WindowsCredentialStore
    chosen = backend()
    if not isinstance(chosen, WindowsCredentialStore):
        raise WorkflowError("Credential hardening is only needed for the Windows store")
    updated = 0
    for name in NAMES:
        value = store_call(chosen.get_password, service(account), name)
        if value is not None:
            store_call(chosen.set_password, service(account), name, value)
            updated += 1
    return {"status": "hardened", "credentials_updated": updated}
