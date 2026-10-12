"""Offline setup, secret persistence and balance decisions. Never use real vaults."""
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import providers
import secure_store
import setup_access
import workflow
from workflow import Account, WorkflowError


class MemoryVault:
    def __init__(self):
        self.items = {}
        self.writes = 0

    def get_password(self, service, name):
        return self.items.get((service, name))

    def set_password(self, service, name, value):
        self.items[service, name] = value
        self.writes += 1

    def delete_password(self, service, name):
        del self.items[service, name]


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.vault = MemoryVault()
        self.store = secure_store.CredentialStore(self.vault)
        self.account = Account("setup-test", self.tmp.name)
        with self.account.locked(create=True):
            self.account.initialize({"sms_max_total_usd": "2.00"})
        self.directory = self.account.root / ".connections"
        self.directory.mkdir()
        self.inbox = "synthetic-test@agentmail.to"
        self.key = "synthetic-key-never-a-real-credential"

    def request(self, method, route, payload=None, **kwargs):
        if method == "POST" and route == "agent/sign-up":
            self.assertTrue(kwargs["anonymous"])
            self.assertNotIn("human_email", payload)
            return {"api_key": self.key, "organization_id": "synthetic-org", "inbox_id": self.inbox}
        if route.startswith("inboxes/"):
            return {"inbox_id": self.inbox}
        self.fail("Unexpected provider operation")

    def connect(self, **kwargs):
        return setup_access.email_connect(self.account, self.store, self.directory,
                                          request=kwargs.pop("request", self.request), **kwargs)

    def client(self, balance="2.00", price="0.75"):
        return SimpleNamespace(
            account=SimpleNamespace(balance=balance, me=Mock(return_value=SimpleNamespace(username="owner@example.invalid"))),
            services=SimpleNamespace(list=Mock(return_value=[SimpleNamespace(service_name="amazon", capability=SimpleNamespace(value="sms"))])),
            verifications=SimpleNamespace(pricing=Mock(return_value=SimpleNamespace(price=price)), create=Mock()),
            session=SimpleNamespace(close=Mock()))

    def test_bootstrap_once_reuses_key_and_inbox_from_fresh_store(self):
        request = Mock(side_effect=self.request)
        self.connect(allow_signup=True, request=request)
        self.account.load()
        self.store = secure_store.CredentialStore(self.vault)
        self.connect(allow_signup=True, request=request)
        signups = [c for c in request.call_args_list if c.args[:2] == ("POST", "agent/sign-up")]
        self.assertEqual(len(signups), 1)
        self.assertEqual(self.account.state["inbox"]["email"], self.inbox)
        self.assertEqual(self.account.state["phase"], "new")
        self.assertEqual(self.account.state["sms"], [])
        for file in Path(self.tmp.name).rglob("*.json"):
            self.assertNotIn(self.key, file.read_text(encoding="utf-8"))
        self.assertNotIn(self.key, json.dumps(setup_access.status(self.account, self.store)))

    def test_signup_requires_explicit_flag(self):
        request = Mock()
        with self.assertRaises(WorkflowError): self.connect(request=request)
        request.assert_not_called()

    def test_unavailable_vault_prevents_signup(self):
        self.store.probe = Mock(side_effect=WorkflowError("Vault locked"))
        request = Mock()
        with self.assertRaises(WorkflowError): self.connect(allow_signup=True, request=request)
        request.assert_not_called()

    def test_timeout_or_storage_failure_never_repeats_signup(self):
        for fail_save in (False, True):
            with self.subTest(fail_save=fail_save):
                intent = self.directory / "agentmail-signup.json"
                intent.unlink(missing_ok=True)
                if fail_save:
                    self.store.write = Mock(side_effect=WorkflowError("save failed"))
                    request = Mock(side_effect=self.request)
                else:
                    request = Mock(side_effect=TimeoutError)
                with self.assertRaises(WorkflowError): self.connect(allow_signup=True, request=request)
                with self.assertRaises(WorkflowError): self.connect(allow_signup=True, request=request)
                self.assertEqual(request.call_count, 1)

    def test_crash_after_vault_save_recovers_binding_without_signup(self):
        self.store.write("agentmail", {"api_key": self.key, "bootstrap_owner": str(self.account.path),
                         "bootstrap_inbox": {"email": self.inbox, "inbox_id": self.inbox}})
        workflow.write_json(self.directory / "agentmail-signup.json", {"status": "pending"})
        request = Mock(side_effect=self.request)
        self.connect(allow_signup=True, request=request)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0], "GET")
        self.assertEqual(self.account.state["inbox"]["email"], self.inbox)

    def test_missing_key_cannot_replace_existing_inbox(self):
        self.account.state["inbox"] = {"inbox_id": self.inbox, "email": self.inbox}
        request = Mock()
        with self.assertRaises(WorkflowError): self.connect(allow_signup=True, request=request)
        request.assert_not_called()

    def test_rejected_existing_key_does_not_provision(self):
        self.store.write("agentmail", {"api_key": self.key})
        self.account.state["inbox"] = {"inbox_id": self.inbox, "email": self.inbox}
        request = Mock(side_effect=WorkflowError("authentication rejected"))
        with self.assertRaises(WorkflowError): self.connect(allow_signup=True, request=request)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0], "GET")
        self.assertEqual(self.store.read("agentmail")["api_key"], self.key)

    def test_existing_key_is_checked_before_creating_an_inbox(self):
        self.store.write("agentmail", {"api_key": self.key})
        # A failed auth check must not mutate provider state.
        request = Mock(side_effect=WorkflowError("authentication rejected"))
        with self.assertRaises(WorkflowError): self.connect(request=request)
        self.assertTrue(all(call.args[0] == "GET" for call in request.call_args_list))

    def test_existing_connection_creates_one_inbox_without_signup(self):
        self.store.write("agentmail", {"api_key": self.key})
        def respond(method, route, payload=None, **kwargs):
            if method == "GET" and route == "inboxes?limit=1":
                return {"inboxes": []}
            if method == "POST" and route == "inboxes":
                return {"inbox_id": self.inbox}
            return self.request(method, route, payload, **kwargs)
        request = Mock(side_effect=respond)
        self.connect(request=request)
        self.connect(request=request)
        self.assertEqual(sum(c.args[:2] == ("POST", "inboxes") for c in request.call_args_list), 1)
        self.assertFalse(any(c.args[1] == "agent/sign-up" for c in request.call_args_list))

    def test_failed_probe_roundtrip_stops_before_signup(self):
        self.vault.get_password = Mock(return_value=None)
        request = Mock()
        with self.assertRaises(WorkflowError): self.connect(allow_signup=True, request=request)
        request.assert_not_called()

    def test_bootstrap_inbox_cannot_be_assigned_to_another_workflow(self):
        self.store.write("agentmail", {"api_key": self.key, "bootstrap_owner": "/different/account",
                         "bootstrap_inbox": {"email": self.inbox, "inbox_id": self.inbox}})
        request = Mock()
        with self.assertRaises(WorkflowError): self.connect(request=request)
        request.assert_not_called()

    def test_environment_override_is_complete_and_does_not_mix_accounts(self):
        self.store.write("textverified", {"api_key": "stored", "username": "stored-user"})
        with self.assertRaises(WorkflowError):
            secure_store.resolve("textverified", self.store, {"TEXTVERIFIED_API_KEY": "override"})
        record = secure_store.resolve("textverified", self.store,
                   {"TEXTVERIFIED_API_KEY": "override", "TEXTVERIFIED_API_USERNAME": "override-user"})
        self.assertEqual(record, {"api_key": "override", "username": "override-user"})

    def test_native_storage_never_uses_discovered_or_plaintext_backend(self):
        with patch.object(secure_store.sys, "platform", "win32"), patch("windows_credentials.WindowsCredentialStore.native") as native:
            self.assertIs(secure_store.native_backend(), native.return_value)
            native.assert_called_once()
        for platform, module, name in (("darwin", "keyring.backends.macOS", "Keyring"),
                                      ("linux", "keyring.backends.SecretService", "Keyring")):
            backend = SimpleNamespace(priority=1)
            factory = Mock(return_value=backend)
            with patch.object(secure_store.sys, "platform", platform), patch.object(importlib, "import_module", return_value=SimpleNamespace(**{name: factory})) as imported:
                self.assertIs(secure_store.native_backend(), backend)
                imported.assert_called_once_with(module)
        with patch.object(secure_store.sys, "platform", "unsupported"):
            with self.assertRaises(WorkflowError): secure_store.native_backend()

    def test_legacy_account_keys_are_reused_without_chat_or_provider_calls(self):
        import credential_store
        old_service = credential_store.service(self.account)
        self.vault.set_password(old_service, "AGENTMAIL_API_KEY", self.key)
        self.vault.set_password(old_service, "TEXTVERIFIED_API_KEY", "legacy-tv-key")
        self.vault.set_password(old_service, "TEXTVERIFIED_API_USERNAME", "owner@example.invalid")
        self.vault.set_password("unrelated-service", "unrelated-name", "untouched")
        result = secure_store.migrate_legacy(self.account, self.store)
        self.assertEqual(result["providers"], {"agentmail": "migrated", "textverified": "migrated"})
        self.assertEqual(self.store.read("agentmail")["api_key"], self.key)
        self.assertNotIn(self.key, json.dumps(result))
        self.assertEqual(self.vault.get_password("unrelated-service", "unrelated-name"), "untouched")
        self.assertEqual(secure_store.migrate_legacy(self.account, self.store)["providers"]["agentmail"], "reused")

    def test_legacy_partial_pair_is_not_silently_replaced_or_mixed(self):
        import credential_store
        self.vault.set_password(credential_store.service(self.account), "TEXTVERIFIED_API_KEY", "partial")
        with self.assertRaises(WorkflowError): secure_store.migrate_legacy(self.account, self.store)
        self.assertIsNone(self.store.read("textverified"))

    def test_saved_sms_opt_out_blocks_new_purchase(self):
        self.account.config["sms_enabled"] = False
        self.account.state["phase"] = "signup"
        client = self.client()
        with self.assertRaises(WorkflowError): providers.phone_create(self.account, client, "amazon")
        client.verifications.create.assert_not_called()
        with self.assertRaises(WorkflowError): self.account.reserve_sms("0.75", "amazon", "verification")
        self.assertEqual(self.account.state["sms"], [])

    def test_saved_sms_opt_out_does_not_require_textverified_to_register(self):
        self.connect(allow_signup=True)
        self.account.config["sms_enabled"] = False
        self.account.state.update(phase="waiting_day_two", day_two_date="2020-01-02", profile_verified_at="proof")
        client_factory = Mock()
        setup_access.begin_signup(self.account, self.store, self.directory, None, self.request, client_factory)
        client_factory.assert_not_called()
        self.assertEqual(self.account.state["phase"], "signup")

    def test_corrupt_vault_is_not_treated_as_missing_access(self):
        self.vault.items[secure_store.SERVICE, "agentmail"] = "not valid json"
        request = Mock()
        with self.assertRaises(WorkflowError): self.connect(allow_signup=True, request=request)
        request.assert_not_called()

    def test_clipboard_capture_saves_pair_without_returning_key(self):
        clipboard = SimpleNamespace(paste=Mock(return_value=self.key), copy=Mock())
        result = setup_access.capture_textverified("owner@example.invalid", self.store,
                    clipboard=clipboard, client_factory=Mock(return_value=self.client()))
        self.assertNotIn(self.key, json.dumps(result))
        self.assertEqual(self.store.read("textverified")["api_key"], self.key)
        clipboard.copy.assert_called_once_with("")

    def test_clipboard_capture_leaves_newer_clipboard_untouched(self):
        clipboard = SimpleNamespace(paste=Mock(side_effect=[self.key, "new unrelated clipboard"]), copy=Mock())
        setup_access.capture_textverified("owner@example.invalid", self.store,
                    clipboard=clipboard, client_factory=Mock(return_value=self.client()))
        clipboard.copy.assert_not_called()

    def test_capture_does_not_replace_key_or_save_mismatched_account(self):
        record = {"api_key": "existing", "username": "owner@example.invalid"}
        self.store.write("textverified", record)
        clipboard = SimpleNamespace(paste=Mock(return_value=self.key), copy=Mock())
        with self.assertRaises(WorkflowError):
            setup_access.capture_textverified("owner@example.invalid", self.store, clipboard=clipboard)
        self.assertEqual(self.store.read("textverified"), record)
        with self.assertRaises(WorkflowError):
            setup_access.save_record("textverified", {"api_key": self.key, "username": "different@example.invalid"},
                                     self.store, replace=True, client_factory=Mock(return_value=self.client()))
        self.assertEqual(self.store.read("textverified"), record)

    def test_balance_floor_and_live_price_are_independent_of_spending_cap(self):
        for balance, price, required, ready in (("0.74", "0.50", "0.75", False),
                                                 ("0.75", "0.75", "0.75", True),
                                                 ("0.90", "1.10", "1.10", False)):
            client = self.client(balance, price)
            result = providers.phone_readiness(self.account, client, "amazon")
            self.assertEqual(result["required_balance_usd"], required)
            self.assertEqual(result["ready"], ready)
            client.verifications.create.assert_not_called()
        self.account.config["sms_max_total_usd"] = None
        self.assertFalse(providers.phone_readiness(self.account, self.client(), "amazon")["ready"])
        self.account.config["sms_max_total_usd"] = "0.50"
        self.assertFalse(providers.phone_readiness(self.account, self.client(), "amazon")["budget_ok"])

    def test_insufficient_balance_prevents_purchase_and_reservation(self):
        self.account.state["phase"] = "signup"
        client = self.client("0.10")
        with self.assertRaises(WorkflowError): providers.phone_create(self.account, client, "amazon")
        client.verifications.create.assert_not_called()
        self.assertEqual(self.account.state["sms"], [])

    def test_existing_allocation_is_reused_without_balance_or_purchase(self):
        self.account.state["phase"] = "signup"
        existing = {"status": "allocated", "kind": "verification", "service": "amazon", "provider_id": "existing"}
        self.account.state["sms"] = [existing]
        client = Mock()
        self.assertIs(providers.phone_create(self.account, client, "amazon"), existing)
        self.assertEqual(client.mock_calls, [])

    def test_day_two_gate_rechecks_balance_before_phase_change(self):
        self.connect(allow_signup=True)
        self.store.write("textverified", {"api_key": self.key, "username": "owner@example.invalid"})
        self.account.state.update(phase="waiting_day_two", day_two_date="2020-01-02", profile_verified_at="proof")
        with self.assertRaises(WorkflowError):
            setup_access.begin_signup(self.account, self.store, self.directory, "amazon", self.request,
                                      Mock(return_value=self.client("0.10")))
        self.assertEqual(self.account.state["phase"], "waiting_day_two")
        setup_access.begin_signup(self.account, self.store, self.directory, "amazon", self.request,
                                  Mock(return_value=self.client()))
        self.assertEqual(self.account.state["phase"], "signup")

    def test_setup_during_browsing_or_after_completion_cannot_provision(self):
        for phase, timer in (("browsing", "active"), ("complete", None)):
            self.account.state.update(phase=phase, active_since=timer)
            request = Mock()
            with self.assertRaises(WorkflowError): self.connect(allow_signup=True, request=request)
            request.assert_not_called()

    def test_shared_connection_lock_blocks_overlapping_setup(self):
        with setup_access.connection_lock(self.account):
            with self.assertRaises(WorkflowError):
                with setup_access.connection_lock(self.account): self.fail("duplicate lock")

    def test_http_error_messages_do_not_leak_provider_bodies_or_keys(self):
        for code, message in ((401, "authentication"), (403, "permission"), (429, "temporarily"), (503, "temporarily")):
            error = HTTPError("https://test.invalid/" + self.key, code, self.key, {}, None)
            with patch.object(providers, "build_opener") as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(WorkflowError) as caught:
                    providers.agentmail_request("GET", "inboxes", credential={"api_key": self.key})
            self.assertIn(message, str(caught.exception))
            self.assertNotIn(self.key, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
