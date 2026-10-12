"""Windows vault replacement, migration, and persistence regression tests."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import credential_store as store
from windows_credentials import WindowsCredentialStore
from workflow import Account


class NativeError(Exception):
    def __init__(self, code):
        self.winerror = code


class FakeWindowsAPI:
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2

    def __init__(self):
        self.records = {}
        self.fail_write = False
        self.fail_delete = False

    def CredRead(self, TargetName, Type):
        if TargetName not in self.records:
            raise NativeError(1168)
        return dict(self.records[TargetName])

    def CredWrite(self, record, flags):
        if self.fail_write:
            raise NativeError(5)
        record = dict(record)
        record["CredentialBlob"] = record["CredentialBlob"].encode("utf-16")
        self.records[record["TargetName"]] = record

    def CredDelete(self, TargetName, Type):
        if self.fail_delete:
            raise NativeError(5)
        if self.records.pop(TargetName, None) is None:
            raise NativeError(1168)

    def seed(self, target, name, value):
        self.records[target] = {"TargetName": target, "UserName": name,
                                "CredentialBlob": value.encode("utf-16"), "Persist": 3}


class WindowsStoreTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeWindowsAPI()
        self.vault = WindowsCredentialStore(self.api, NativeError)
        self.service = "AmazonShoppingSkill/test/disposable"
        self.name = store.NAMES[0]

    def test_replacement_leaves_one_local_entry_with_only_new_value(self):
        self.vault.set_password(self.service, self.name, "before")
        self.vault.set_password(self.service, self.name, "after")
        self.assertEqual(len(self.api.records), 1)
        record = next(iter(self.api.records.values()))
        self.assertEqual(record["Persist"], 2)
        self.assertEqual(self.vault._value(record), "after")
        self.assertEqual(self.vault.get_password(self.service, self.name), "after")

    def test_legacy_base_wins_until_saved_and_stale_copy_is_replaced(self):
        self.api.seed(self.service, self.name, "latest")
        self.api.seed(self.vault.legacy_target(self.service, self.name), self.name, "stale")
        self.assertEqual(self.vault.get_password(self.service, self.name), "latest")
        self.vault.set_password(self.service, self.name, "replacement")
        self.assertNotIn(self.service, self.api.records)
        self.assertEqual(len(self.api.records), 1)
        self.assertEqual(self.vault.get_password(self.service, self.name), "replacement")

    def test_saving_one_field_preserves_other_field_in_shared_legacy_slot(self):
        other = store.NAMES[1]
        self.api.seed(self.service, other, "other-secret")
        self.vault.set_password(self.service, self.name, "replacement")
        self.assertEqual(self.vault.get_password(self.service, other), "other-secret")
        self.assertEqual(self.vault.get_password(self.service, self.name), "replacement")

    def test_failed_write_never_removes_previous_value(self):
        self.api.seed(self.service, self.name, "latest")
        self.api.fail_write = True
        with self.assertRaises(NativeError):
            self.vault.set_password(self.service, self.name, "replacement")
        self.assertEqual(self.vault.get_password(self.service, self.name), "latest")
        self.assertEqual(len(self.api.records), 1)

    def test_failed_cleanup_is_reported_and_retry_removes_old_copy(self):
        self.api.seed(self.service, self.name, "latest")
        self.api.fail_delete = True
        with patch.object(store, "backend", return_value=self.vault):
            with self.assertRaises(store.StoreError):
                store.store_call(self.vault.set_password, self.service, self.name, "replacement")
        # The new value is saved, but a cleanup failure is never called success.
        self.assertEqual(self.vault.get_password(self.service, self.name), "replacement")
        self.api.fail_delete = False
        self.vault.set_password(self.service, self.name, "replacement")
        self.assertNotIn(self.service, self.api.records)
        self.assertEqual(self.vault.get_password(self.service, self.name), "replacement")

    def test_full_migration_keeps_latest_values_and_removes_legacy_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            account = Account("test", tmp)
            service = store.service(account)
            for name in store.NAMES:
                self.api.seed(self.vault.legacy_target(service, name), name, "saved-" + name)
            self.api.seed(service, store.NAMES[2], "latest-username")
            with patch.object(store, "backend", return_value=self.vault):
                self.assertEqual(store.harden_windows(account)["credentials_updated"], 3)
            self.assertNotIn(service, self.api.records)
            self.assertEqual(len(self.api.records), 3)
            self.assertTrue(all(record["Persist"] == 2 for record in self.api.records.values()))
            self.assertEqual(self.vault.get_password(service, store.NAMES[2]), "latest-username")
            self.assertEqual(self.vault.get_password(service, store.NAMES[0]), "saved-" + store.NAMES[0])

    def test_missing_credential_returns_none_and_denial_is_not_hidden(self):
        self.assertIsNone(self.vault.get_password(self.service, self.name))
        with patch.object(self.api, "CredRead", side_effect=NativeError(5)):
            with self.assertRaises(NativeError):
                self.vault.get_password(self.service, self.name)

    def test_other_platform_hardening_does_not_modify_credentials(self):
        with patch.object(store, "backend", return_value=object()):
            with self.assertRaisesRegex(store.WorkflowError, "Windows"):
                store.harden_windows(Account("test", "."))

    def test_delete_removes_only_requested_credential(self):
        self.api.seed(self.service, store.NAMES[1], "other")
        self.vault.set_password(self.service, self.name, "test")
        self.vault.delete_password(self.service, self.name)
        self.assertEqual(len(self.api.records), 1)
        self.assertEqual(self.vault.get_password(self.service, store.NAMES[1]), "other")


@unittest.skipUnless(sys.platform == "win32" and os.environ.get("AMAZON_SHOPPING_NATIVE_STORE_TEST") == "1",
                     "Opt-in disposable Windows vault integration test")
class NativeWindowsStoreTests(unittest.TestCase):
    def test_real_vault_migration_and_replacement(self):
        from keyring.backends.Windows import WinVaultKeyring
        legacy = WinVaultKeyring()
        vault = store.backend()
        self.assertIsInstance(vault, WindowsCredentialStore)
        service = "AmazonShoppingSkill/audit/" + uuid.uuid4().hex
        try:
            for name in store.NAMES:
                legacy.set_password(service, name, "synthetic-" + name)
            legacy.set_password(service, store.NAMES[2], "synthetic-latest")
            for name in store.NAMES:
                value = vault.get_password(service, name)
                vault.set_password(service, name, value)
            self.assertIsNone(vault._read(service))
            self.assertTrue(all(vault._read(vault.legacy_target(service, name)) is None for name in store.NAMES))
            self.assertEqual(vault.get_password(service, store.NAMES[2]), "synthetic-latest")
            for name in store.NAMES:
                vault.set_password(service, name, "synthetic-replaced")
                record = vault._read(vault.target(service, name))
                self.assertEqual(record["Persist"], 2)
                self.assertEqual(vault._value(record), "synthetic-replaced")
            self.assertIsNone(vault._read(service))
        finally:
            for name in store.NAMES:
                vault.delete_password(service, name)
        self.assertIsNone(vault._read(service))
        self.assertTrue(all(vault._read(vault.target(service, name)) is None for name in store.NAMES))
        self.assertTrue(all(vault._read(vault.legacy_target(service, name)) is None for name in store.NAMES))


if __name__ == "__main__":
    unittest.main()
