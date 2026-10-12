"""Offline tests of consequential decisions; never create accounts or call providers."""
from datetime import datetime, timedelta, timezone
import getpass
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import workflow
import providers
from workflow import Account, WorkflowError, validate_config


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.time = datetime(2026, 10, 12, 16, 0, tzinfo=timezone.utc)
        self.clock = patch.object(workflow, "now", side_effect=lambda: self.time)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.a = Account("shopping-01", self.tmp.name)
        with self.a.locked(create=True):
            self.a.initialize({"product_allowlist": ["Desk lamp", "Notebook", "Mug"]})

    def begin(self):
        self.a.verify_profile(str(self.a.path / "chrome-data/Default"))
        return self.a.browse_start()

    def finish_day_one(self):
        self.begin()
        self.a.viewed("Desk lamp", "https://www.amazon.com/dp/TEST")
        self.time += timedelta(seconds=300)
        self.a.browse_stop("completed")

    def signup(self):
        self.finish_day_one()
        self.time += timedelta(days=1)
        self.a.signup_start()

    def sms_config(self, budget="2.00", attempts=1):
        self.a.config.update(sms_mode="verification", sms_max_total_usd=budget, sms_max_allocations=attempts)
        workflow.write_json(self.a.config_path, self.a.config)

    def test_reinitialization_does_not_overwrite(self):
        self.begin()
        self.a.initialize({"product_allowlist": ["Wrong"]})
        self.assertEqual(self.a.state["phase"], "browsing")
        self.assertIn("Desk lamp", self.a.config["product_allowlist"])

    def test_manual_resume_uses_disk_state_without_scheduler_or_session(self):
        self.finish_day_one()
        resumed = Account("shopping-01", self.tmp.name)
        resumed.load()
        self.time += timedelta(days=1)
        resumed.signup_start()
        resumed.state["inbox"] = {"inbox_id": "fake-inbox", "email": "test@example.invalid"}
        result = resumed.complete("Simulated observed confirmation")
        self.assertEqual(result["phase"], "complete")
        self.assertIsNone(result["schedule"])
        self.assertFalse(result["schedule_cleanup_required"])

    def test_bundled_defaults_are_ready_without_product_input(self):
        config = validate_config({})
        names = config["product_allowlist"]
        self.assertEqual(len(names), 50)
        self.assertEqual(len(set(names)), 50)
        self.assertIn("foam plates", names)
        self.assertIn("label maker tape", names)
        self.assertIn("grill brush", names)
        sample = Path(__file__).resolve().parents[1] / "assets/config.example.json"
        account = Account("bundled-defaults", self.tmp.name)
        with account.locked(create=True):
            account.initialize(json.loads(sample.read_text(encoding="utf-8")))
            account.verify_profile(str(account.path / "chrome-data/Default"))
            account.browse_start()
            account.viewed("foam plates", "https://www.amazon.com/dp/PLATES")
            with self.assertRaises(WorkflowError):
                account.viewed("television", "https://www.amazon.com/dp/TV")
            account.load()
            self.assertEqual(account.config["product_allowlist"], names)

    def test_explicit_allowlist_override_is_preserved(self):
        self.assertEqual(validate_config({"product_allowlist": ["Custom lamp"]})["product_allowlist"], ["Custom lamp"])

    def test_explicit_empty_override_does_not_silently_expand_scope(self):
        self.assertEqual(validate_config({"product_allowlist": []})["product_allowlist"], [])

    def test_one_time_mode_is_default_and_normalizes_legacy_null(self):
        for config in ({}, {"sms_mode": None}):
            validated = validate_config(config)
            self.assertEqual(validated["sms_mode"], "verification")
            self.assertIsNone(validated["sms_max_total_usd"])

    def test_rental_config_is_rejected(self):
        with self.assertRaises(WorkflowError):
            validate_config({"sms_mode": "rental", "sms_max_total_usd": "5.00"})

    def test_rental_ledger_reservation_is_rejected(self):
        self.signup(); self.sms_config()
        with self.assertRaises(WorkflowError):
            self.a.reserve_sms("1.00", "amazon", "rental")
        self.assertEqual(self.a.state["sms"], [])

    def test_phone_client_cannot_reuse_rental_or_call_provider_in_rental_mode(self):
        self.signup(); self.sms_config()
        client = Mock()
        self.a.config["sms_mode"] = "rental"
        with self.assertRaises(WorkflowError):
            providers.phone_create(self.a, client, "amazon")
        self.a.config["sms_mode"] = "verification"
        self.a.state["sms"] = [{"status": "allocated", "kind": "rental", "service": "amazon", "provider_id": "legacy-rental"}]
        with self.assertRaises(WorkflowError):
            providers.phone_create(self.a, client, "amazon")
        with self.assertRaises(WorkflowError):
            providers.active_phone(self.a)
        self.assertEqual(client.mock_calls, [])

    def test_path_traversal_and_windows_device_names_rejected(self):
        for name in ("../evil", "x/y", "CON", "con", "nul", "com1", "..", "a "):
            with self.subTest(name=name), self.assertRaises(WorkflowError):
                Account(name, self.tmp.name)

    def test_platform_data_directories(self):
        home = Path(self.tmp.name) / "Home With Spaces"
        local = Path(self.tmp.name) / "Windows Local"
        self.assertEqual(workflow.data_directory("win32", {"LOCALAPPDATA": str(local)}, home), local / "AmazonShoppingSkill")
        self.assertEqual(workflow.data_directory("win32", {}, home), home / "AppData/Local/AmazonShoppingSkill")
        # A stale Windows environment variable must not override Mac paths.
        self.assertEqual(workflow.data_directory("darwin", {"LOCALAPPDATA": str(local)}, home), home / "Library/Application Support/AmazonShoppingSkill")

    def test_environment_report_resolves_mac_runtime_without_creating_files(self):
        home = Path(self.tmp.name) / "Mac Home"
        with patch.object(workflow.sys, "platform", "darwin"), patch.object(Path, "home", return_value=home):
            report = workflow.environment_info()
        self.assertEqual(Path(report["runtime_python"]), home / "Library/Application Support/AmazonShoppingSkill/runtime/bin/python")
        self.assertFalse(home.exists())
        self.assertEqual(report["platform"], "darwin")

    def test_mac_chrome_discovery_includes_user_applications(self):
        home = Path(self.tmp.name) / "Mac Home"
        candidates = workflow.chrome_candidates("darwin", {}, home)
        self.assertIn(home / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome", candidates)

    def test_mac_launcher_quotes_spaces_and_shell_characters(self):
        argv = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--user-data-dir=/Users/O'Neil/Library/Application Support/$(unsafe)", "chrome://version"]
        with patch.object(Path, "chmod", autospec=True) as chmod:
            launcher = workflow.write_browser_launcher(self.a.path, argv, "darwin")
        text = launcher.read_text(encoding="utf-8")
        self.assertEqual(launcher.name, "open-browser.command")
        self.assertEqual(shlex.split(text.splitlines()[1][len("exec "):]), argv)
        self.assertEqual(chmod.call_args.args[1], 0o700)

    def test_windows_launcher_quotes_every_argument(self):
        argv = ["C:\\Programs\\Chrome.exe", "--user-data-dir=C:\\A&B\\%name%", "chrome://version"]
        launcher = workflow.write_browser_launcher(self.a.path, argv, "win32")
        text = launcher.read_text(encoding="utf-8")
        self.assertEqual(launcher.name, "open-browser.cmd")
        self.assertIn('"--user-data-dir=C:\\A&B\\%%name%%"', text)
        self.assertIn("DisableDelayedExpansion", text)
        with self.assertRaises(WorkflowError):
            workflow.write_browser_launcher(self.a.path, ['bad\ncommand'], "win32")

    def test_launch_uses_platform_shortcut_and_invalidates_profile_before_spawn(self):
        chrome = Path(self.tmp.name) / "Chrome With Spaces"
        chrome.touch()
        for platform, suffix in (("win32", ".cmd"), ("darwin", ".command")):
            self.a.state["profile_verified_at"] = "previous-session"
            self.a.save()
            def check_launch(argv, **kwargs):
                stored = json.loads(self.a.state_path.read_text(encoding="utf-8"))
                self.assertIsNone(stored["profile_verified_at"])
                self.assertEqual(argv[0], str(chrome))
                self.assertIn("--user-data-dir=" + str(self.a.path / "chrome-data"), argv)
                self.assertNotIn("shell", kwargs)
            with patch.object(workflow.sys, "platform", platform), patch.object(workflow, "chrome_candidates", return_value=[chrome]), patch.object(workflow.subprocess, "Popen", side_effect=check_launch), patch.object(Path, "chmod", autospec=True):
                result = self.a.launch()
            self.assertTrue(result["shortcut"].endswith(suffix))

    def test_unsupported_platform_cannot_launch(self):
        with patch.object(workflow.sys, "platform", "unknown"), patch.object(workflow.subprocess, "Popen") as spawn:
            with self.assertRaises(WorkflowError): self.a.launch()
            spawn.assert_not_called()

    def test_hidden_credential_input_only_requests_relevant_provider(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(providers.sys.stdin, "isatty", return_value=True), patch.object(providers.getpass, "getpass", return_value="synthetic-test-key") as prompt:
            providers.prompt_credentials("email-create")
            self.assertEqual(os.environ["AGENTMAIL_API_KEY"], "synthetic-test-key")
            self.assertNotIn("TEXTVERIFIED_API_KEY", os.environ)
            self.assertEqual(prompt.call_count, 1)

    def test_existing_credentials_are_not_requested_again(self):
        values = {"TEXTVERIFIED_API_KEY": "synthetic", "TEXTVERIFIED_API_USERNAME": "test-user"}
        with patch.dict(os.environ, values, clear=True), patch.object(providers.sys.stdin, "isatty", return_value=False), patch.object(providers.getpass, "getpass") as prompt:
            providers.prompt_credentials("phone-services")
            prompt.assert_not_called()

    def test_missing_credentials_require_interactive_terminal(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(providers.sys.stdin, "isatty", return_value=False), patch.object(providers.getpass, "getpass") as prompt:
            with self.assertRaises(WorkflowError): providers.prompt_credentials("email-create")
            prompt.assert_not_called()

    def test_hidden_input_does_not_fall_back_to_echoing(self):
        import warnings
        def unavailable(*args):
            warnings.warn("Hidden input unavailable", getpass.GetPassWarning)
        with patch.dict(os.environ, {}, clear=True), patch.object(providers.sys.stdin, "isatty", return_value=True), patch.object(providers.getpass, "getpass", side_effect=unavailable):
            with self.assertRaises(WorkflowError): providers.prompt_credentials("email-create")
            self.assertNotIn("AGENTMAIL_API_KEY", os.environ)

    def test_lock_prevents_concurrent_mutation(self):
        with self.a.locked():
            with self.assertRaises(WorkflowError):
                with self.a.locked():
                    self.fail("Acquired lock twice")
        self.assertFalse((self.a.path / ".lock").exists())

    def test_default_personal_profile_is_rejected(self):
        with self.assertRaises(WorkflowError):
            self.a.verify_profile("C:/personal/chrome/Default")

    def test_allowlist_and_profile_required(self):
        with self.assertRaises(WorkflowError): self.a.browse_start()
        self.a.verify_profile(str(self.a.path / "chrome-data/Default"))
        self.a.config["product_allowlist"] = []
        with self.assertRaises(WorkflowError): self.a.browse_start()

    def test_signup_and_inbox_forbidden_day_one(self):
        self.begin()
        with self.assertRaises(WorkflowError): self.a.signup_start()
        request = Mock()
        with self.assertRaises(WorkflowError): providers.email_create(self.a, request)
        request.assert_not_called()

    def test_calendar_gate_not_24_hour_delay(self):
        self.time = datetime(2026, 10, 13, 6, 58, tzinfo=timezone.utc)  # Oct 12 23:58 PDT
        self.finish_day_one()  # completes Oct 13 00:03 PDT
        self.assertEqual(self.a.state["day_two_date"], "2026-10-13")
        self.a.signup_start()
        self.assertEqual(self.a.state["phase"], "signup")

    def test_same_day_signup_rejected_after_browsing(self):
        self.finish_day_one()
        with self.assertRaises(WorkflowError): self.a.signup_start()

    def test_timer_pause_resume_counts_no_paused_time(self):
        self.begin()
        self.time += timedelta(seconds=75)
        self.a.browse_stop("interrupted")
        self.time += timedelta(hours=2)
        self.assertEqual(self.a.status()["remaining_seconds"], 225)
        self.a.browse_start()
        self.time += timedelta(seconds=25)
        self.assertEqual(self.a.status()["remaining_seconds"], 200)

    def test_crash_recovery_does_not_count_unknown_idle(self):
        self.begin()
        self.time += timedelta(hours=1)
        self.a.browse_stop("interrupted", recovered_seconds=40)
        self.assertEqual(self.a.status()["remaining_seconds"], 260)

    def test_invalid_recovery_time_cannot_corrupt_state(self):
        self.begin()
        self.time += timedelta(seconds=60)
        for value in (float("nan"), float("inf"), -1, 61):
            with self.subTest(value=value), self.assertRaises(WorkflowError):
                self.a.browse_stop("interrupted", recovered_seconds=value)

    def test_cannot_complete_on_timer_alone(self):
        self.begin()
        self.time += timedelta(seconds=300)
        with self.assertRaises(WorkflowError): self.a.browse_stop("completed")

    def test_actions_stop_at_deadline(self):
        self.begin()
        self.time += timedelta(seconds=300)
        with self.assertRaises(WorkflowError): self.a.viewed("Desk lamp", "https://www.amazon.com/dp/TEST")

    def test_cart_scope_duplicates_and_cap(self):
        self.begin()
        with self.assertRaises(WorkflowError): self.a.cart_intent("Television", "https://www.amazon.com/dp/TV")
        with self.assertRaises(WorkflowError): self.a.cart_intent("Desk lamp", "https://example.com/dp/LAMP")
        first = self.a.cart_intent("Desk lamp", "https://www.amazon.com/dp/LAMP")
        with self.assertRaises(WorkflowError): self.a.cart_intent("Desk lamp", "https://www.amazon.com/dp/LAMP")
        second = self.a.cart_intent("Notebook", "https://www.amazon.com/dp/BOOK")
        self.a.cart_result(first["id"], "confirmed")
        self.a.cart_result(second["id"], "confirmed")
        with self.assertRaises(WorkflowError): self.a.cart_intent("Mug", "https://www.amazon.com/dp/MUG")
        self.assertEqual(self.a.status()["confirmed_cart_additions"], 2)

    def test_unresolved_cart_prevents_signup(self):
        self.begin()
        self.a.viewed("Desk lamp", "https://www.amazon.com/dp/LAMP")
        self.a.cart_intent("Desk lamp", "https://www.amazon.com/dp/LAMP")
        self.time += timedelta(seconds=300)
        self.a.browse_stop("completed")
        self.time += timedelta(days=1)
        with self.assertRaises(WorkflowError): self.a.signup_start()

    def test_budget_required_and_exact_decimal_limit(self):
        self.signup()
        with self.assertRaises(WorkflowError): self.a.reserve_sms("0.01", "amazon", "verification")
        self.sms_config("0.30", 2)
        one = self.a.reserve_sms("0.10", "amazon", "verification")
        self.a.sms_result(one["id"], "failed")
        self.a.reserve_sms("0.20", "amazon", "verification")
        self.assertEqual(self.a.status()["sms_reserved_usd"], "0.30")

    def test_cancel_does_not_reset_budget_or_attempts(self):
        self.signup(); self.sms_config()
        entry = self.a.reserve_sms("1.00", "amazon", "verification")
        self.a.sms_result(entry["id"], "cancelled")
        with self.assertRaises(WorkflowError): self.a.reserve_sms("0.10", "amazon", "verification")

    def test_email_retry_reuses_idempotency_key(self):
        self.signup()
        request = Mock(side_effect=TimeoutError)
        with self.assertRaises(TimeoutError): providers.email_create(self.a, request)
        key = self.a.state["inbox_client_id"]
        self.a.load()
        request = Mock(return_value={"inbox_id": "inbox-1", "email": "test@agentmail.to"})
        providers.email_create(self.a, request)
        self.assertEqual(request.call_args.args[2]["client_id"], key)
        providers.email_create(self.a, request)
        self.assertEqual(request.call_count, 1)

    def test_phone_timeout_blocks_second_purchase(self):
        self.signup(); self.sms_config()
        client = SimpleNamespace(
            services=SimpleNamespace(list=Mock(return_value=[SimpleNamespace(service_name="amazon", capability=SimpleNamespace(value="sms"))])),
            verifications=SimpleNamespace(pricing=Mock(return_value=SimpleNamespace(price=1)), create=Mock(side_effect=TimeoutError)))
        with self.assertRaises(WorkflowError): providers.phone_create(self.a, client, "amazon")
        self.a.load()
        self.assertEqual(self.a.state["sms"][0]["status"], "uncertain")
        with self.assertRaises(WorkflowError): providers.phone_create(self.a, client, "amazon")
        self.assertEqual(client.verifications.create.call_count, 1)

    def test_over_budget_never_calls_purchase(self):
        self.signup(); self.sms_config("0.50")
        client = SimpleNamespace(
            services=SimpleNamespace(list=Mock(return_value=[SimpleNamespace(service_name="amazon", capability=SimpleNamespace(value="sms"))])),
            verifications=SimpleNamespace(pricing=Mock(return_value=SimpleNamespace(price=1)), create=Mock()))
        with self.assertRaises(WorkflowError): providers.phone_create(self.a, client, "amazon")
        client.verifications.create.assert_not_called()

    def test_unknown_service_never_calls_purchase(self):
        self.signup(); self.sms_config()
        client = SimpleNamespace(services=SimpleNamespace(list=Mock(return_value=[])), verifications=SimpleNamespace(create=Mock()))
        with self.assertRaises(WorkflowError): providers.phone_create(self.a, client, "amazon")
        client.verifications.create.assert_not_called()

    def test_nan_and_infinite_costs_rejected(self):
        for value in ("NaN", "Infinity", "-1"):
            with self.subTest(value=value), self.assertRaises(WorkflowError): workflow.money(value)

    def test_completion_requires_inbox_and_observation(self):
        self.signup()
        with self.assertRaises(WorkflowError): self.a.complete("Signed in")
        self.a.state["inbox"] = {"email": "user@agentmail.to", "inbox_id": "1"}
        with self.assertRaises(WorkflowError): self.a.complete("")
        self.a.complete("Signed-in account page shows intended email")
        with self.assertRaises(WorkflowError): self.a.browse_start()
        self.assertEqual(self.a.state["phase"], "complete")


if __name__ == "__main__":
    unittest.main()
