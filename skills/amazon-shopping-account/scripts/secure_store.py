"""Provider credentials: environment injection or an explicitly selected OS vault.

No plaintext fallback, interactive input, UI, or secret-bearing command arguments.
"""
from __future__ import annotations

import importlib
import hashlib
import json
import os
import sys
import uuid

from workflow import WorkflowError

SERVICE = "AmazonShoppingSkill"
FIELDS = {
    "agentmail": {"api_key": "AGENTMAIL_API_KEY"},
    "textverified": {"api_key": "TEXTVERIFIED_API_KEY", "username": "TEXTVERIFIED_API_USERNAME"},
}


def native_backend():
    # Instantiate only shipped OS backends. Do not let plugin discovery choose
    # a plaintext, null, chained, or third-party backend automatically.
    classes = {
        "win32": ("keyring.backends.Windows", "WinVaultKeyring"),
        "darwin": ("keyring.backends.macOS", "Keyring"),
        "linux": ("keyring.backends.SecretService", "Keyring"),
    }
    try:
        if sys.platform == "win32":
            from windows_credentials import WindowsCredentialStore
            return WindowsCredentialStore.native()
        if sys.platform == "linux":
            for module, name in (("keyring.backends.SecretService", "Keyring"),
                                 ("keyring.backends.kwallet", "DBusKeyring"),
                                 ("keyring.backends.kwallet", "DBusKeyringKWallet4")):
                try:
                    candidate = getattr(importlib.import_module(module), name)()
                    if candidate.priority > 0:
                        return candidate
                except Exception:
                    continue
            raise RuntimeError
        module, name = classes[sys.platform]
        backend = getattr(importlib.import_module(module), name)()
        if backend.priority <= 0:
            raise RuntimeError
        return backend
    except Exception:
        raise WorkflowError("Secure OS storage unavailable; unlock the user vault or use an approved secret injector") from None


def validate_record(provider, record):
    if not isinstance(record, dict) or any(
        not isinstance(record.get(field), str) or not record[field].strip()
        or len(record[field]) > 16384 or any(c in record[field] for c in "\r\n\x00")
        for field in FIELDS[provider]
    ):
        raise WorkflowError("Invalid provider credential record; reconnect this provider")
    return record


class CredentialStore:
    def __init__(self, backend=None):
        self._backend = backend

    @property
    def backend(self):
        if self._backend is None:
            self._backend = native_backend()
        return self._backend

    def read(self, provider):
        try:
            raw = self.backend.get_password(SERVICE, provider)
            return validate_record(provider, json.loads(raw)) if raw is not None else None
        except WorkflowError:
            raise
        except Exception:
            raise WorkflowError("Cannot read secure provider storage; unlock the user vault") from None

    def write(self, provider, record):
        validate_record(provider, record)
        try:
            self.backend.set_password(SERVICE, provider, json.dumps(record))
            if self.read(provider) != record:
                raise RuntimeError
        except Exception:
            raise WorkflowError("Secure credential save was not confirmed; preserve state and do not repeat signup") from None

    def probe(self):
        """Confirm writable storage before a one-shot provisioning request."""
        name, value = "probe-" + uuid.uuid4().hex, uuid.uuid4().hex
        try:
            self.backend.set_password(SERVICE, name, value)
            if self.backend.get_password(SERVICE, name) != value:
                raise RuntimeError
            self.backend.delete_password(SERVICE, name)
        except Exception:
            raise WorkflowError("Secure storage is not writable; resolve it before creating an inbox") from None


def resolve(provider, store=None, environ=None):
    environ = os.environ if environ is None else environ
    fields = FIELDS[provider]
    present = [bool(environ.get(name)) for name in fields.values()]
    if any(present):
        if not all(present):
            raise WorkflowError("Incomplete injected credentials; provide the matching key and account email together")
        return validate_record(provider, {field: environ[name] for field, name in fields.items()})
    return (store or CredentialStore()).read(provider)


def require(provider):
    record = resolve(provider)
    if record is None:
        raise WorkflowError(f"{provider} connection missing; resume initial setup")
    return record


def migrate_legacy(account, store=None):
    """Copy only this account's older native entries; never enumerate the vault."""
    store = store or CredentialStore()
    digest = hashlib.sha256(str(account.path).encode()).hexdigest()[:24]
    old_service = f"AmazonShoppingSkill/{account.account_id}/{digest}"
    result = {}
    for provider, fields in FIELDS.items():
        if provider == "textverified" and not account.config["sms_enabled"]:
            continue
        if resolve(provider, store) is not None:
            result[provider] = "reused"
            continue
        try:
            record = {field: store.backend.get_password(old_service, name) for field, name in fields.items()}
        except Exception:
            raise WorkflowError("Cannot read previous credential storage; unlock it before continuing") from None
        if not any(record.values()):
            result[provider] = "missing"
            continue
        validate_record(provider, record)
        store.write(provider, record)
        result[provider] = "migrated"
    return {"status": "checked", "providers": result}
