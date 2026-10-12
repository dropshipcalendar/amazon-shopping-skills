"""Private setup tests use temporary accounts and fake native stores only."""
import contextlib
import getpass
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import credential_store as store
import providers
import setup_ui
import workflow

spec = importlib.util.spec_from_file_location("shopping_setup", Path(__file__).resolve().parents[1] / "scripts/setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class FakeStore:
    def __init__(self):
        self.values = {}

    def get_password(self, service, name):
        return self.values.get((service, name))

    def set_password(self, service, name, value):
        self.values[service, name] = value


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = FakeStore()
        self.patch = patch.object(store, "backend", return_value=self.backend)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.account, self.launcher = setup.prepare(root=self.tmp.name, timezone="Europe/London")

    def test_prepare_requires_no_credentials_or_network(self):
        result = setup.report(self.account)
        self.assertEqual(result["phase"], "new")
        self.assertTrue(result["sms_enabled"])
        self.assertEqual(result["sms_budget_status"], "pending")
        self.assertEqual(result["day_one_readiness"], "requires_live_browser_check")
        self.assertIsNone(self.account.state["inbox"])
        self.assertFalse(self.account.state["sms"])
        self.assertFalse(self.backend.values)

    def test_prepare_uses_detected_timezone_for_new_account(self):
        with patch.object(setup, "detected_timezone", return_value="Asia/Tokyo"):
            account, _ = setup.prepare("other", self.tmp.name)
        self.assertEqual(account.config["timezone"], "Asia/Tokyo")

    def test_repeated_prepare_preserves_settings_and_progress(self):
        setup.save_settings(self.account, {"sms_enabled": False})
        self.account.verify_profile(str(self.account.path / "chrome-data/Default"))
        self.account.browse_start()
        with patch.object(setup, "detected_timezone", side_effect=AssertionError("should not detect")):
            again, _ = setup.prepare(root=self.tmp.name, timezone="Asia/Tokyo", marketplace="https://www.amazon.co.jp")
        self.assertEqual(again.config["timezone"], "Europe/London")
        self.assertEqual(again.config["marketplace"], "https://www.amazon.com")
        self.assertFalse(again.config["sms_enabled"])
        self.assertEqual(again.state["phase"], "browsing")

    def test_settings_only_save_does_not_touch_vault(self):
        with patch.object(store, "backend", side_effect=AssertionError("no vault needed")):
            result = setup.save_settings(self.account, {"sms_enabled": True})
        self.assertIsNotNone(result["setup_saved_at"])
        self.assertIsNone(self.account.state["inbox"])
        self.assertIsNone(self.account.state["schedule"])

    def test_minimal_form_saves_only_filled_credentials_and_preserves_settings(self):
        setup.save_settings(self.account, {"sms_enabled": False, "sms_max_total_usd": "2.50"}, approve_sms_budget=True)
        store.save(self.account, {store.NAMES[0]: "old", store.NAMES[1]: "retained"})
        before = dict(self.account.config)
        fields = dict(zip(store.NAMES, ("new", "", "test-user")))
        setup_ui.save_credentials(self.account, fields, setup.save_settings)
        self.assertEqual(self.account.config, before)
        self.assertEqual(store.read(self.account, store.NAMES[0]), "new")
        self.assertEqual(store.read(self.account, store.NAMES[1]), "retained")
        self.assertEqual(store.read(self.account, store.NAMES[2]), "test-user")

    def test_blank_minimal_form_does_not_approve_spending(self):
        fields = dict.fromkeys(store.NAMES, "")
        setup_ui.save_credentials(self.account, fields, setup.save_settings)
        self.assertTrue(self.account.config["sms_enabled"])
        self.assertIsNone(self.account.config["sms_max_total_usd"])
        self.assertFalse(self.backend.values)

    def test_budget_requires_acceptance_before_any_secret_write(self):
        with self.assertRaisesRegex(workflow.WorkflowError, "Accept"):
            setup.save_settings(self.account, {"sms_max_total_usd": "2.50"}, {store.NAMES[0]: "fake-key"})
        self.assertFalse(self.backend.values)
        self.assertIsNone(self.account.load().config["sms_max_total_usd"])
        setup.save_settings(self.account, {"sms_max_total_usd": "2.50"}, approve_sms_budget=True)
        setup.save_settings(self.account, {"sms_max_total_usd": "2.50"})
        self.assertEqual(self.account.config["sms_max_total_usd"], "2.50")

    def test_invalid_settings_do_not_save_secrets(self):
        with self.assertRaises(workflow.WorkflowError):
            setup.save_settings(self.account, {"timezone": "invalid"}, {store.NAMES[0]: "fake-key"})
        self.assertFalse(self.backend.values)

    def test_cannot_change_marketplace_after_browsing(self):
        self.account.verify_profile(str(self.account.path / "chrome-data/Default"))
        self.account.browse_start()
        with self.assertRaisesRegex(workflow.WorkflowError, "cannot change"):
            setup.save_settings(self.account, {"marketplace": "https://www.amazon.co.uk"})

    def test_credentials_not_written_to_runtime_files_or_status(self):
        fake_key = "synthetic-secret-only-in-fake-vault"
        result = setup.save_settings(self.account, {}, {store.NAMES[0]: fake_key})
        result["credentials"] = store.status(self.account)
        self.assertNotIn(fake_key, json.dumps(result))
        for path in self.account.path.rglob("*"):
            if path.is_file():
                self.assertNotIn(fake_key.encode(), path.read_bytes())
        self.assertEqual(store.read(self.account, store.NAMES[0]), fake_key)

    def test_blank_credentials_preserve_and_replace_is_explicit(self):
        store.save(self.account, {store.NAMES[0]: "old"})
        store.save(self.account, {})
        with self.assertRaisesRegex(workflow.WorkflowError, "explicitly"):
            store.save(self.account, {store.NAMES[0]: "new"})
        self.assertEqual(store.read(self.account, store.NAMES[0]), "old")
        store.save(self.account, {store.NAMES[0]: "new"}, replace=True)
        self.assertEqual(store.read(self.account, store.NAMES[0]), "new")

    def test_store_names_are_scoped_to_account_and_root(self):
        other = workflow.Account("shopping-02", self.tmp.name)
        elsewhere = workflow.Account("shopping-01", Path(self.tmp.name) / "elsewhere")
        self.assertEqual(len({store.service(self.account), store.service(other), store.service(elsewhere)}), 3)

    def test_rejects_unknown_names_and_multiline_values(self):
        for values in ({"AMAZON_PASSWORD": "no"}, {store.NAMES[0]: "bad\nkey"}):
            with self.assertRaises(workflow.WorkflowError): store.save(self.account, values)
        self.assertFalse(self.backend.values)

    def test_provider_invocations_load_vault_and_restore_environment(self):
        store.save(self.account, {store.NAMES[0]: "vault-key"})
        for _ in range(2):
            with store.helper_environment(self.account, (store.NAMES[0],)):
                self.assertEqual(providers.secret(store.NAMES[0]), "vault-key")
            self.assertNotIn(store.NAMES[0], os.environ)

    def test_injected_environment_takes_precedence(self):
        os.environ[store.NAMES[0]] = "injected"
        with patch.object(store, "read", side_effect=AssertionError("do not read vault")):
            with store.helper_environment(self.account, (store.NAMES[0],)):
                self.assertEqual(providers.secret(store.NAMES[0]), "injected")
        self.assertEqual(os.environ[store.NAMES[0]], "injected")

    def test_prompted_secret_is_removed_after_helper_failure(self):
        with patch.object(store, "read", return_value=None):
            with self.assertRaises(RuntimeError):
                with store.helper_environment(self.account, (store.NAMES[0],)):
                    os.environ[store.NAMES[0]] = "prompted"
                    raise RuntimeError("request failed")
        self.assertNotIn(store.NAMES[0], os.environ)

    def test_locked_store_status_is_actionable_and_sanitized(self):
        class KeyringLocked(Exception): pass
        self.backend.get_password = Mock(side_effect=KeyringLocked("private-value"))
        statuses = store.status(self.account)
        self.assertTrue(all(v["status"] == "locked" for v in statuses.values()))
        self.assertNotIn("private-value", json.dumps(statuses))

    def test_backend_allowlist_rejects_plaintext_and_unknown(self):
        self.patch.stop()
        for platform in ("win32", "darwin", "linux", "unknown"):
            with patch.object(store.sys, "platform", platform), patch("keyring.get_keyring", return_value=FakeStore()):
                with self.assertRaises(store.StoreError): store.backend()
        self.patch.start()

    def test_backend_allowlist_accepts_native_classes(self):
        self.patch.stop()
        for platform, names in store.BACKENDS.items():
            for name in names:
                module, classname = name.rsplit(".", 1)
                native = type(classname, (), {"__module__": module})()
                with patch.object(store.sys, "platform", platform), patch("keyring.get_keyring", return_value=native):
                    if platform == "win32":
                        from windows_credentials import WindowsCredentialStore
                        with patch.object(WindowsCredentialStore, "native", return_value=self.backend):
                            self.assertIs(store.backend(), self.backend)
                    else:
                        self.assertIs(store.backend(), native)
        self.patch.start()

    def test_status_does_not_read_vault_without_request(self):
        with patch.object(store, "status", side_effect=AssertionError("no unlock prompt")):
            setup.report(self.account)

    def test_chain_uses_native_backend_without_plaintext_fallback(self):
        self.patch.stop()
        native = type("Keyring", (), {"__module__": "keyring.backends.SecretService"})()
        chain = type("ChainerBackend", (), {"__module__": "keyring.backends.chainer", "backends": [FakeStore(), native]})()
        with patch.object(store.sys, "platform", "linux"), patch("keyring.get_keyring", return_value=chain):
            self.assertIs(store.backend(), native)
        self.patch.start()

    def test_provider_cli_loads_credentials_in_each_invocation(self):
        self.account.state["phase"] = "signup"
        self.account.save()
        store.save(self.account, {store.NAMES[0]: "cli-vault-key"})
        def action(*args):
            self.assertEqual(providers.secret(store.NAMES[0]), "cli-vault-key")
            return {"status": "synthetic-ok"}
        for command, extra, function in (("email-create", [], "email_create"), ("email-messages", ["--after", "2026-10-12T00:00:00Z"], "email_messages")):
            argv = ["providers.py", "--root", self.tmp.name, command, self.account.account_id, *extra]
            with patch.object(sys, "argv", argv), patch.object(providers, function, side_effect=action), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(providers.main(), 0)
            self.assertNotIn("cli-vault-key", output.getvalue())
            self.assertNotIn(store.NAMES[0], os.environ)

    def test_provider_cli_rejects_day_one_before_reading_credentials(self):
        argv = ["providers.py", "--root", self.tmp.name, "email-create", self.account.account_id]
        with patch.object(sys, "argv", argv), patch.object(store, "read", side_effect=AssertionError("must not read")), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(providers.main(), 2)

    def test_legacy_defaults_and_explicit_sms_opt_out(self):
        self.assertTrue(workflow.validate_config({})["sms_enabled"])
        self.assertFalse(workflow.validate_config({"sms_enabled": False})["sms_enabled"])
        for value in (1, "true", None):
            with self.assertRaises(workflow.WorkflowError): workflow.validate_config({"sms_enabled": value})

    def test_no_fake_day_one_readiness_from_old_profile_observation(self):
        self.account.verify_profile(str(self.account.path / "chrome-data/Default"))
        self.assertEqual(setup.report(self.account)["day_one_readiness"], "requires_live_browser_check")

    def test_sms_disabled_blocks_purchase_before_provider_call(self):
        self.account.state["phase"] = "signup"
        self.account.config.update(sms_enabled=False, sms_max_total_usd="5")
        client = Mock()
        with self.assertRaises(workflow.WorkflowError): providers.phone_create(self.account, client, "amazon")
        client.verifications.create.assert_not_called()
        with self.assertRaises(workflow.WorkflowError): self.account.reserve_sms("1", "amazon", "verification")

    def test_existing_allocation_freezes_budget_settings(self):
        self.account.state["sms"] = [{"status": "uncertain"}]
        self.account.save()
        with self.assertRaisesRegex(workflow.WorkflowError, "allocation attempt"):
            setup.save_settings(self.account, {"sms_max_total_usd": "50"}, approve_sms_budget=True)

    def test_terminal_refuses_captured_input_without_echo(self):
        with patch.object(setup.sys.stdin, "isatty", return_value=False), patch.object(setup.getpass, "getpass") as prompt:
            with self.assertRaises(workflow.WorkflowError): setup.hidden_input("Key: ")
            prompt.assert_not_called()

    def test_hidden_input_fails_instead_of_echoing(self):
        import warnings
        def warning(*args): warnings.warn("unsafe echo", getpass.GetPassWarning)
        with patch.object(setup.sys.stdin, "isatty", return_value=True), patch.object(setup.getpass, "getpass", side_effect=warning):
            with self.assertRaises(workflow.WorkflowError): setup.hidden_input("Key: ")

    def test_local_browser_form_does_not_require_tkinter(self):
        with patch.dict(sys.modules, {"tkinter": None}):
            with patch.object(setup_ui, "show_setup") as show:
                setup.gui_setup(self.account)
                show.assert_called_once()

    def test_launchers_quote_paths_and_use_correct_platform_suffix(self):
        for platform, suffix in (("win32", ".cmd"), ("darwin", ".command"), ("linux", ".sh")):
            with patch.object(Path, "chmod", autospec=True):
                path = setup.write_launcher(self.account, platform)
            self.assertTrue(str(path).endswith(suffix))
            text = path.read_text()
            if platform != "win32":
                argv = shlex.split(text.splitlines()[1][len("exec "):])
                self.assertEqual(argv[-2:], ["open", self.account.account_id])
            else:
                self.assertIn("DisableDelayedExpansion", text)

    def test_completed_workflow_is_preserved(self):
        self.account.state["phase"] = "complete"
        self.account.save()
        with self.assertRaisesRegex(workflow.WorkflowError, "complete"):
            setup.save_settings(self.account, {"sms_enabled": False})


if __name__ == "__main__":
    unittest.main()
