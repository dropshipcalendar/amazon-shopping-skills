"""Local schedule bookkeeping tests. No live scheduler or browser is invoked."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import workflow
from workflow import Account, WorkflowError


class SchedulingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.time = datetime(2026, 10, 12, 16, 0, tzinfo=timezone.utc)
        clock = patch.object(workflow, "now", side_effect=lambda: self.time)
        clock.start()
        self.addCleanup(clock.stop)
        self.a = Account("schedule-test", self.tmp.name)
        with self.a.locked(create=True):
            self.a.initialize({})

    def prepare(self):
        return self.a.schedule_prepare("test-chat", "09:00")

    def record(self, intent_id, automation_id):
        return self.a.schedule_record(intent_id, automation_id, self.a.state["schedule"]["first_run_at"])

    def active(self):
        intent = self.prepare()
        return self.record(intent["intent_id"], "fake-automation")

    def complete(self):
        # Supply simulated completion evidence rather than run either live day.
        self.a.state["phase"] = "signup"
        self.a.state["inbox"] = {"inbox_id": "fake-inbox", "email": "example@example.invalid"}
        return self.a.complete("Simulated observed confirmation")

    def test_prepare_is_persistent_and_idempotent(self):
        first = self.prepare().copy()
        self.a.load()
        second = self.prepare()
        self.assertEqual(first, second)
        self.assertEqual(second["status"], "create_pending")
        self.assertIsNone(second["automation_id"])
        self.assertEqual(second["first_run_at"], "2026-10-13T09:00:00-07:00")

    def finish_day_one(self):
        self.a.verify_profile(str(self.a.path / "chrome-data/Default"))
        self.a.browse_start()
        self.a.viewed("desk lamp", "https://www.amazon.com/dp/TEST")
        self.time += timedelta(minutes=5)
        return self.a.browse_stop("completed")

    def test_default_day_one_is_five_minutes_away_and_retry_does_not_drift(self):
        first = self.a.schedule_prepare("test-chat").copy()
        self.assertEqual(first["step"], "day-one")
        self.assertEqual(first["first_run_at"], "2026-10-12T09:05:00-07:00")
        self.time += timedelta(minutes=10)
        self.a.load()
        self.assertEqual(first, self.a.schedule_prepare("test-chat"))

    def test_day_one_absolute_override_requires_future_aware_time(self):
        for value in ("bad", "2026-10-12T10:00:00", "2026-10-12T08:59:00-07:00"):
            with self.subTest(value=value), self.assertRaises(WorkflowError):
                self.a.schedule_prepare("test-chat", run_at=value)
            self.assertIsNone(self.a.state["schedule"])
        intent = self.a.schedule_prepare("test-chat", run_at="2026-10-13T00:30:00+00:00")
        self.assertEqual(intent["first_run_at"], "2026-10-12T17:30:00-07:00")

    def test_default_delay_crosses_midnight_and_dst_by_elapsed_time(self):
        for current, expected in (
            (datetime(2026, 10, 13, 6, 58, tzinfo=timezone.utc), "2026-10-13T00:03:00-07:00"),
            (datetime(2026, 3, 8, 9, 58, tzinfo=timezone.utc), "2026-03-08T03:03:00-07:00"),
            (datetime(2026, 11, 1, 8, 58, tzinfo=timezone.utc), "2026-11-01T01:03:00-08:00"),
        ):
            with self.subTest(current=current):
                self.time = current
                self.a.state["schedule"] = None
                self.assertEqual(self.a.schedule_prepare("test-chat")["first_run_at"], expected)

    def test_record_requires_verified_execution_time(self):
        intent = self.a.schedule_prepare("test-chat")
        for value in (None, "2026-10-12T09:05:00"):
            with self.subTest(value=value), self.assertRaises(WorkflowError):
                self.a.schedule_record(intent["intent_id"], "fake", value)
        mismatch = self.a.schedule_record(intent["intent_id"], "fake", "2026-10-12T09:06:00-07:00")
        self.assertEqual(mismatch["status"], "timing_mismatch")
        self.a.load()
        self.assertEqual(self.a.state["schedule"]["automation_id"], "fake")
        with self.assertRaises(WorkflowError):
            self.a.schedule_record(intent["intent_id"], "replacement", intent["first_run_at"])
        saved = self.a.schedule_record(intent["intent_id"], "fake", "2026-10-12T16:05:00+00:00")
        self.assertEqual(saved["status"], "active")
        self.assertEqual(saved["confirmed_run_at"], intent["first_run_at"])

    def test_confirmation_distinguishes_repeated_dst_hour(self):
        self.time = datetime(2026, 11, 1, 7, 0, tzinfo=timezone.utc)
        intent = self.a.schedule_prepare("test-chat", run_at="2026-11-01T01:30:00-07:00")
        saved = self.a.schedule_record(intent["intent_id"], "fake", "2026-11-01T01:30:00-08:00")
        self.assertEqual(saved["status"], "timing_mismatch")
        self.assertEqual(saved["automation_id"], "fake")

    def test_day_two_explicit_clock_time_is_preserved_on_late_resume(self):
        self.finish_day_one()
        self.time = datetime(2026, 10, 15, 18, 0, tzinfo=timezone.utc)
        intent = self.a.schedule_prepare("test-chat", "10:00", step="day-two")
        self.assertEqual(intent["first_run_at"], "2026-10-16T10:00:00-07:00")

    def test_existing_legacy_record_accepts_id_without_new_time_requirement(self):
        intent = self.prepare()
        del intent["step"]
        self.a.save()
        self.a.load()
        result = self.a.schedule_record(intent["intent_id"], "legacy-task")
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["automation_id"], "legacy-task")

    def test_day_two_requires_completion_and_confirmed_day_one_cleanup(self):
        with self.assertRaises(WorkflowError): self.a.schedule_prepare("test-chat", step="day-two")
        self.active()
        status = self.finish_day_one()
        self.assertTrue(status["schedule_cleanup_required"])
        with self.assertRaises(WorkflowError): self.a.schedule_prepare("test-chat", step="day-two")
        self.a.schedule_result("remove", "fake-automation", "uncertain")
        with self.assertRaises(WorkflowError): self.a.schedule_prepare("test-chat", step="day-two")
        self.a.schedule_result("remove", "fake-automation", "confirmed")
        second = self.a.schedule_prepare("test-chat", step="day-two").copy()
        self.assertEqual(second["first_run_at"], "2026-10-13T09:00:00-07:00")
        self.assertEqual(len(self.a.state["schedule_history"]), 1)
        self.assertEqual(self.a.state["schedule_history"][0]["automation_id"], "fake-automation")
        self.record(second["intent_id"], "fake-day-two")
        self.a.load()
        self.assertEqual(self.a.schedule_prepare("test-chat"), self.a.state["schedule"])
        self.assertEqual(len(self.a.state["schedule_history"]), 1)
        with self.assertRaises(WorkflowError): self.a.schedule_action("remove", "fake-automation")
        self.complete()
        self.a.schedule_result("remove", "fake-day-two", "confirmed")
        self.assertFalse(self.a.status()["schedule_cleanup_required"])

    def test_day_two_uses_completion_date_after_midnight_and_late_resume(self):
        self.time = datetime(2026, 10, 13, 6, 58, tzinfo=timezone.utc)
        self.finish_day_one()
        with self.assertRaises(WorkflowError):
            self.a.schedule_prepare("test-chat", step="day-two", run_at="2026-10-13T09:00:00-07:00")
        self.time = datetime(2026, 10, 16, 18, 0, tzinfo=timezone.utc)
        intent = self.a.schedule_prepare("test-chat", step="day-two")
        self.assertEqual(intent["first_run_at"], "2026-10-16T11:05:00-07:00")

    def test_lost_day_one_creation_is_reconciled_before_day_two(self):
        intent = self.a.schedule_prepare("test-chat").copy()
        self.a.schedule_creation_result(intent["intent_id"], "uncertain")
        self.finish_day_one()
        self.assertTrue(self.a.status()["schedule_cleanup_required"])
        with self.assertRaises(WorkflowError): self.a.schedule_prepare("test-chat", step="day-two")
        saved = self.record(intent["intent_id"], "recovered-day-one")
        self.assertEqual(saved["status"], "removal_pending")
        with self.assertRaises(WorkflowError): self.a.schedule_action("resume", "recovered-day-one")
        self.a.schedule_result("remove", "recovered-day-one", "confirmed")
        self.assertEqual(self.a.schedule_prepare("test-chat", step="day-two")["step"], "day-two")

    def test_confirmed_absent_day_one_allows_day_two_without_new_day_one(self):
        intent = self.a.schedule_prepare("test-chat").copy()
        self.finish_day_one()
        self.a.schedule_creation_result(intent["intent_id"], "confirmed_absent")
        self.assertEqual(self.a.state["schedule"]["status"], "removed")
        self.assertEqual(self.a.schedule_prepare("test-chat", step="day-two")["step"], "day-two")

    def test_prepare_cannot_replace_target_time_or_timezone(self):
        self.prepare()
        for chat, time in (("different-chat", "09:00"), ("test-chat", "10:00")):
            with self.assertRaises(WorkflowError): self.a.schedule_prepare(chat, time)
        self.a.config["timezone"] = "UTC"
        with self.assertRaises(WorkflowError): self.prepare()

    def test_runner_target_needs_no_chat_id_and_survives_reload(self):
        first = self.a.schedule_prepare("local-agent-runner", "09:00", "runner").copy()
        self.a.load()
        self.assertEqual(first, self.a.schedule_prepare("local-agent-runner", "09:00", "runner"))
        self.assertEqual(first["target_kind"], "runner")
        self.assertEqual(first["target_id"], "local-agent-runner")
        self.assertNotIn("thread_id", first)
        with self.assertRaises(WorkflowError):
            self.a.schedule_prepare("local-agent-runner", "09:00", "session")

    def test_legacy_session_record_is_reused_without_losing_automation(self):
        self.active()
        saved = self.a.state["schedule"]
        saved["thread_id"] = saved.pop("target_id")
        del saved["target_kind"]
        del saved["step"]
        saved.pop("confirmed_run_at", None)
        self.a.save()
        self.a.load()
        result = self.prepare()
        self.assertEqual(result["automation_id"], "fake-automation")
        self.assertEqual(result["thread_id"], "test-chat")

    def test_invalid_target_does_not_create_schedule(self):
        for target, kind in (("", "session"), ("runner", "unknown")):
            with self.assertRaises(WorkflowError):
                self.a.schedule_prepare(target, "09:00", kind)
        self.assertIsNone(self.a.state["schedule"])

    def test_record_requires_matching_intent_and_id(self):
        intent = self.prepare()
        with self.assertRaises(WorkflowError): self.record("wrong-intent", "fake-automation")
        with self.assertRaises(WorkflowError): self.record(intent["intent_id"], "")
        self.record(intent["intent_id"], "fake-automation")
        self.assertEqual(self.record(intent["intent_id"], "fake-automation")["status"], "active")
        with self.assertRaises(WorkflowError): self.record(intent["intent_id"], "replacement-id")

    def test_uncertain_creation_does_not_make_a_new_intent(self):
        intent = self.prepare().copy()
        self.a.schedule_creation_result(intent["intent_id"], "uncertain")
        self.a.load()
        second = self.prepare()
        self.assertEqual(second["intent_id"], intent["intent_id"])
        self.assertEqual(second["status"], "uncertain")
        self.a.schedule_creation_result(intent["intent_id"], "confirmed_absent")
        self.assertEqual(self.prepare()["intent_id"], intent["intent_id"])
        self.assertEqual(self.a.state["schedule"]["status"], "create_pending")

    def test_completion_requests_removal_without_claiming_remote_success(self):
        self.active()
        result = self.complete()
        self.assertEqual(result["phase"], "complete")
        self.assertTrue(result["schedule_cleanup_required"])
        self.assertEqual(result["schedule"]["status"], "removal_pending")
        self.a.load()
        self.assertEqual(self.a.state["schedule"]["automation_id"], "fake-automation")

    def test_removal_failure_preserves_completed_work_and_pending_cleanup(self):
        self.active(); self.complete()
        self.a.schedule_result("remove", "fake-automation", "uncertain")
        self.a.load()
        result = self.a.status()
        self.assertEqual(result["phase"], "complete")
        self.assertTrue(result["schedule_cleanup_required"])
        self.assertEqual(result["schedule"]["pending_action"], "remove")
        with self.assertRaises(WorkflowError): self.a.browse_start()

    def test_confirmed_removal_is_idempotent_and_does_not_delete_profile(self):
        self.active(); self.complete()
        self.a.schedule_result("remove", "fake-automation", "confirmed")
        self.a.schedule_result("remove", "fake-automation", "confirmed")
        self.assertFalse(self.a.status()["schedule_cleanup_required"])
        self.assertEqual(self.a.state["schedule"]["status"], "removed")
        self.assertTrue((self.a.path / "chrome-data").is_dir())
        self.assertTrue(self.a.state_path.is_file())

    def test_wrong_automation_cannot_be_mutated(self):
        self.active()
        with self.assertRaises(WorkflowError): self.a.schedule_action("remove", "someone-elses-id")
        with self.assertRaises(WorkflowError): self.a.schedule_result("remove", "someone-elses-id", "confirmed")
        self.assertEqual(self.a.state["schedule"]["status"], "active")

    def test_pause_resume_and_removed_schedule_are_not_silently_reactivated(self):
        self.active()
        self.a.schedule_action("pause", "fake-automation")
        self.a.schedule_result("pause", "fake-automation", "confirmed")
        self.assertEqual(self.prepare()["status"], "paused")
        self.a.schedule_action("resume", "fake-automation")
        self.a.schedule_result("resume", "fake-automation", "confirmed")
        self.assertEqual(self.a.state["schedule"]["status"], "active")
        self.a.schedule_action("remove", "fake-automation")
        self.a.schedule_result("remove", "fake-automation", "confirmed")
        self.assertEqual(self.prepare()["status"], "removed")
        with self.assertRaises(WorkflowError): self.a.schedule_action("resume", "fake-automation")

    def test_results_cannot_skip_pending_action(self):
        self.active()
        with self.assertRaises(WorkflowError): self.a.schedule_result("remove", "fake-automation", "confirmed")
        self.a.schedule_action("pause", "fake-automation")
        with self.assertRaises(WorkflowError): self.a.schedule_action("remove", "fake-automation")

    def test_lost_creation_result_recovered_after_completion_requires_removal(self):
        intent = self.prepare().copy()
        self.a.schedule_creation_result(intent["intent_id"], "uncertain")
        self.complete()
        self.assertTrue(self.a.status()["schedule_cleanup_required"])
        result = self.record(intent["intent_id"], "recovered-automation")
        self.assertEqual(result["status"], "removal_pending")
        self.a.schedule_result("remove", "recovered-automation", "confirmed")
        self.assertFalse(self.a.status()["schedule_cleanup_required"])

    def test_confirmed_absence_can_finish_cleanup_without_an_id(self):
        intent = self.prepare().copy()
        self.complete()
        self.a.schedule_creation_result(intent["intent_id"], "confirmed_absent")
        self.assertFalse(self.a.status()["schedule_cleanup_required"])
        with self.assertRaises(WorkflowError): self.prepare()

    def test_old_state_loads_without_schedule_and_preserves_phase(self):
        del self.a.state["schedule"]
        self.a.state["phase"] = "waiting_day_two"
        self.a.save()
        self.a.load()
        self.assertIsNone(self.a.state["schedule"])
        self.assertEqual(self.a.state["phase"], "waiting_day_two")

    def test_nonexistent_dst_time_rejected_and_ambiguous_time_is_first_occurrence(self):
        self.time = datetime(2026, 3, 7, 16, 0, tzinfo=timezone.utc)
        with self.assertRaises(WorkflowError): self.a.schedule_prepare("test-chat", "02:30")
        self.assertIsNone(self.a.state["schedule"])
        self.time = datetime(2026, 10, 31, 16, 0, tzinfo=timezone.utc)
        schedule = self.a.schedule_prepare("test-chat", "01:30")
        self.assertEqual(schedule["first_run_at"], "2026-11-01T01:30:00-07:00")

    def test_schedule_cli_round_trip_stays_local(self):
        command = [sys.executable, str(Path(workflow.__file__)), "--root", self.tmp.name]
        def run(*args):
            result = subprocess.run(command + list(args), capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        intent = run("schedule-prepare", "schedule-test", "--target-id", "offline-runner", "--target-kind", "runner", "--step", "day-one", "--run-at", future)
        self.assertEqual(intent["target_id"], "offline-runner")
        self.assertEqual(intent["target_kind"], "runner")
        self.assertEqual(intent["step"], "day-one")
        self.assertEqual(datetime.fromisoformat(intent["first_run_at"]), datetime.fromisoformat(future))
        saved = run("schedule-record", "schedule-test", "--intent-id", intent["intent_id"], "--automation-id", "offline-fake-id", "--run-at", intent["first_run_at"])
        self.assertEqual(saved["automation_id"], "offline-fake-id")
        run("schedule-action", "schedule-test", "--automation-id", "offline-fake-id", "--action", "remove")
        removed = run("schedule-result", "schedule-test", "--automation-id", "offline-fake-id", "--action", "remove", "--outcome", "confirmed")
        self.assertEqual(removed["status"], "removed")

    def test_legacy_cli_option_still_addresses_a_session(self):
        command = [sys.executable, str(Path(workflow.__file__)), "--root", self.tmp.name,
                   "schedule-prepare", "schedule-test", "--thread-id", "existing-session", "--local-time", "09:00"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        intent = json.loads(result.stdout)
        self.assertEqual(intent["target_id"], "existing-session")
        self.assertEqual(intent["target_kind"], "session")


if __name__ == "__main__":
    unittest.main()
