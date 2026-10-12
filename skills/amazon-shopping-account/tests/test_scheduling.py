"""Local schedule bookkeeping tests. No live scheduler or browser is invoked."""
from datetime import datetime, timezone
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

    def active(self):
        intent = self.prepare()
        return self.a.schedule_record(intent["intent_id"], "fake-automation")

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

    def test_prepare_cannot_replace_chat_time_or_timezone(self):
        self.prepare()
        for chat, time in (("different-chat", "09:00"), ("test-chat", "10:00")):
            with self.assertRaises(WorkflowError): self.a.schedule_prepare(chat, time)
        self.a.config["timezone"] = "UTC"
        with self.assertRaises(WorkflowError): self.prepare()

    def test_record_requires_matching_intent_and_id(self):
        intent = self.prepare()
        with self.assertRaises(WorkflowError): self.a.schedule_record("wrong-intent", "fake-automation")
        with self.assertRaises(WorkflowError): self.a.schedule_record(intent["intent_id"], "")
        self.a.schedule_record(intent["intent_id"], "fake-automation")
        self.assertEqual(self.a.schedule_record(intent["intent_id"], "fake-automation")["status"], "active")
        with self.assertRaises(WorkflowError): self.a.schedule_record(intent["intent_id"], "replacement-id")

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
        result = self.a.schedule_record(intent["intent_id"], "recovered-automation")
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
        intent = run("schedule-prepare", "schedule-test", "--thread-id", "offline-test-chat", "--local-time", "09:00")
        saved = run("schedule-record", "schedule-test", "--intent-id", intent["intent_id"], "--automation-id", "offline-fake-id")
        self.assertEqual(saved["automation_id"], "offline-fake-id")
        run("schedule-action", "schedule-test", "--automation-id", "offline-fake-id", "--action", "remove")
        removed = run("schedule-result", "schedule-test", "--automation-id", "offline-fake-id", "--action", "remove", "--outcome", "confirmed")
        self.assertEqual(removed["status"], "removed")


if __name__ == "__main__":
    unittest.main()
