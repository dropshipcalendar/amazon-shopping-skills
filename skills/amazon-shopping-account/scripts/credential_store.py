"""Account-scoped native credentials. Never serialize or print secret values."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
import sys

from workflow import WorkflowError

NAMES = ("AGENTMAIL_API_KEY", "TEXTVERIFIED_API_KEY", "TEXTVERIFIED_API_USERNAME")
BACKENDS = {
    "win32": {"keyring.backends.Windows.WinVaultKeyring"},
    "darwin": {"keyring.backends.macOS.Keyring"},
    "linux": {"keyring.backends.SecretService.Keyring", "keyring.backends.kwallet.DBusKeyring",
              "keyring.backends.kwallet.DBusKeyringKWallet4"},
}


class StoreError(WorkflowError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Native credential store {status}; unlock it or use private terminal entry/approved environment injection")


def backend():
    try:
        import keyring
        chosen = keyring.get_keyring()
        identity = type(chosen).__module__ + "." + type(chosen).__name__
        if identity == "keyring.backends.chainer.ChainerBackend":
            for candidate in chosen.backends:
                candidate_id = type(candidate).__module__ + "." + type(candidate).__name__
                if candidate_id in BACKENDS.get(sys.platform, set()):
                    chosen, identity = candidate, candidate_id
                    break
        if identity not in BACKENDS.get(sys.platform, set()):
            raise StoreError("unavailable")
        if sys.platform == "win32":
            from windows_credentials import WindowsCredentialStore
            return WindowsCredentialStore.native()
        return chosen
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


def read(account, name):
    validate_name(name)
    return store_call(backend().get_password, service(account), name)


def save(account, values, replace=False):
    if not values:
        return
    for name, value in values.items():
        validate_name(name)
        if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n\0"):
            raise WorkflowError("Credential fields must contain a nonempty single-line value")
    chosen = backend()
    for name in values:
        if store_call(chosen.get_password, service(account), name) and not replace:
            raise WorkflowError("A credential already exists; explicitly select replacement to change it")
    # Some OS stores have no multi-item transaction. A retry with blank fields
    # preserves any values successfully saved before a backend failure.
    for name, value in values.items():
        store_call(chosen.set_password, service(account), name, value)


def status(account):
    result = {}
    for name in NAMES:
        if os.environ.get(name):
            result[name] = {"status": "configured", "source": "environment"}
            continue
        try:
            result[name] = {"status": "configured" if read(account, name) else "missing", "source": "native_store"}
        except StoreError as exc:
            result[name] = {"status": exc.status, "source": "native_store"}
    return result


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


@contextmanager
def helper_environment(account, names):
    """Inject native credentials only into this helper and restore on exit."""
    previous = {name: os.environ.get(name) for name in names}
    try:
        for name in names:
            validate_name(name)
            if not os.environ.get(name):
                try:
                    value = read(account, name)
                except StoreError:
                    value = None  # Explicit hidden prompting remains available.
                if value:
                    os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
