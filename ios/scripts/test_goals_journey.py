"""Offline crash, wire replay and independent assertion checks for the goal CLI."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location(
    "goals_journey", Path(__file__).with_name("goals-journey.py")
)
journey = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(journey)


def config():
    return {
        "apiURL": journey.API,
        "supabaseURL": journey.AUTH,
        "publicAnonKey": "synthetic-key",
        "users": [
            {"email": "a@example.test", "password": "synthetic-a"},
            {"email": "b@example.test", "password": "synthetic-b"},
        ],
    }


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "private.json"
        self.journal = journey.Journal(self.path, create=True)

    def test_pending_write_replays_exact_bytes_key_owner_and_version_after_restart(self):
        calls = []

        def accepted_but_lost(owner, method, path, body, key):
            disk = json.loads(self.path.read_text())["operations"]["allocation"]
            self.assertEqual(
                (
                    disk["owner"],
                    disk["method"],
                    disk["path"],
                    disk["body"].encode(),
                    disk["key"],
                ),
                (owner, method, path, body, key),
            )
            calls.append((owner, method, path, body, key))
            if len(calls) == 1:
                raise journey.Refused("synthetic accepted response loss")
            return 200, {"goals": [{"goal": {"id": "synthetic-goal"}}], "replayed": True}

        client = Mock(api=Mock(side_effect=accepted_but_lost))
        body = {"expected_version": 2, "amount": "600"}
        with self.assertRaises(journey.Refused):
            self.journal.command(
                client,
                "allocation",
                "PUT",
                journey.GOALS + "/allocations",
                lambda: body,
                owner=1,
            )
        restored = journey.Journal(self.path)
        builder = Mock(
            side_effect=AssertionError("Do not rebuild pending version or token")
        )
        result = restored.command(
            client, "allocation", "PATCH", journey.GOALS + "/allocations", builder
        )
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(calls[1][0], 1)
        self.assertEqual(
            json.loads(calls[1][3]), {"amount": "600", "expected_version": 2}
        )
        self.assertTrue(result["replayed"])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        builder.assert_not_called()

    def test_accepted_command_does_not_rebuild_or_send_after_reload(self):
        client = Mock(
            api=Mock(return_value=(201, {"goal": {"id": "saved"}, "replayed": False}))
        )
        first = self.journal.command(
            client, "goal", "POST", journey.GOALS, lambda: {"target": "1000"}
        )
        before = self.path.read_bytes()
        restored = journey.Journal(self.path)
        builder = Mock(side_effect=AssertionError("Accepted commands are immutable"))
        second = restored.command(client, "goal", "POST", journey.GOALS, builder)
        self.assertEqual(first, second)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(client.api.call_count, 1)
        builder.assert_not_called()

    def test_pending_operation_blocks_unrelated_command_before_builder_or_http(self):
        client = Mock(api=Mock(side_effect=journey.Refused("lost")))
        with self.assertRaises(journey.Refused):
            self.journal.command(
                client, "first", "POST", journey.GOALS, lambda: {"target": "1000"}
            )
        build = Mock()
        with self.assertRaisesRegex(journey.Refused, "Recover pending"):
            self.journal.command(client, "second", "POST", journey.GOALS, build)
        self.assertEqual(client.api.call_count, 1)
        build.assert_not_called()

    def test_money_restart_does_not_refresh_preview_or_mutate_reviewed_token(self):
        preview = {
            "ready": True,
            "reviewed_request": {"amount": "100", "expected_versions": {"account": 2}},
            "preview_token": "reviewed-token",
        }
        client = Mock(api=Mock(side_effect=[(200, preview), journey.Refused("lost")]))
        with self.assertRaises(journey.Refused):
            journey.money(self.journal, client, "money", lambda: {"amount": "100"})
        pending = json.loads(self.path.read_text())["operations"]["money"]
        self.assertEqual(
            json.loads(pending["body"]),
            {
                "amount": "100",
                "expected_versions": {"account": 2},
                "preview_token": "reviewed-token",
            },
        )
        restored = journey.Journal(self.path)
        client.api.reset_mock(side_effect=True)
        client.api.return_value = (
            200,
            {"activity": {"activity_id": "same"}, "replayed": True},
        )
        build = Mock(side_effect=AssertionError("No second preview"))
        journey.money(restored, client, "money", build)
        self.assertEqual(client.api.call_count, 1)
        self.assertEqual(client.api.call_args.args[3], pending["body"].encode())
        self.assertEqual(client.api.call_args.args[4], pending["key"])
        build.assert_not_called()

    def test_atomic_save_failure_sends_nothing(self):
        client = Mock()
        with (
            patch.object(self.journal, "save", side_effect=OSError("disk full")),
            self.assertRaises(OSError),
        ):
            self.journal.command(
                client, "goal", "POST", journey.GOALS, lambda: {"target": "1000"}
            )
        client.api.assert_not_called()

    def test_symlink_and_world_readable_journal_are_rejected(self):
        link = self.path.with_name("link.json")
        link.symlink_to(self.path)
        with self.assertRaises(journey.Refused):
            journey.Journal(link)
        with self.assertRaises(journey.Refused):
            journey.save_private(link, {})
        self.path.chmod(0o644)
        with self.assertRaises(journey.Refused):
            journey.Journal(self.path)

    def test_proxy_committed_response_loss_retries_identical_command(self):
        client = journey.Client(config(), self.journal, response_loss=True)
        client.sessions["0"] = {"access_token": "synthetic-token"}
        requests = []

        def request(url, method, body=None, headers=None):
            if url.endswith("/__fault"):
                return 200, {
                    "armed": method == "POST",
                    "dropped": 0 if method == "POST" else 1,
                }
            pending = json.loads(self.path.read_text())["operations"]["goal"]
            self.assertEqual(pending["body"].encode(), body)
            self.assertEqual(pending["key"], headers["Idempotency-Key"])
            requests.append((url, method, body, headers))
            if len(requests) == 1:
                raise journey.Refused("committed response lost")
            return 201, {"goal": {"id": "one"}, "replayed": True}

        with patch.object(client, "raw", side_effect=request):
            result = self.journal.command(
                client, "goal", "POST", journey.GOALS, lambda: {"target": "1000"}
            )
        self.assertTrue(result["replayed"])
        self.assertEqual(requests[0], requests[1])
        self.assertTrue(self.journal.state["response_loss_verified"])

    def test_proxy_restart_uses_saved_fault_counter_without_rearming(self):
        self.journal.state["fault"] = {"before_dropped": 0, "key": "stable-key"}
        client = journey.Client(config(), self.journal, response_loss=True)
        client.sessions["0"] = {"access_token": "synthetic-token"}

        def request(url, method, body=None, headers=None):
            if url.endswith("/__fault"):
                self.assertEqual(method, "GET")
                return 200, {"armed": False, "dropped": 1}
            return 201, {"goal": {"id": "one"}, "replayed": True}

        with patch.object(client, "raw", side_effect=request):
            client.api(0, "POST", journey.GOALS, b'{"target":"1000"}', "stable-key")
        self.assertTrue(self.journal.state["response_loss_verified"])


class BoundaryTests(unittest.TestCase):
    def test_rejected_configuration_before_http(self):
        for field, bad in (
            ("apiURL", "https://hosted.example/api/v1"),
            ("apiURL", "http://127.0.0.1:59000/api/v1"),
            ("supabaseURL", "http://127.0.0.1:59001"),
        ):
            with self.subTest(field=field, bad=bad), self.assertRaises(journey.Refused):
                journey.Client({**config(), field: bad}, Mock())

    def test_routes_rejected_before_auth(self):
        client = journey.Client(config(), Mock(state={"sessions": {}}))
        with patch.object(client, "authenticate") as authenticate:
            for path in (
                "https://example.test/financial-plan",
                "/auth/login",
                "/financial-plan/../auth",
                "//example.test/financial-plan",
                "/financial-plan/%2e%2e/auth",
                "/financial-planning",
            ):
                with self.subTest(path=path), self.assertRaises(journey.Refused):
                    client.api(0, "POST", path)
            authenticate.assert_not_called()

    def test_literals_reject_stale_original_credit_and_shared_shortfall_priority(self):
        good = {
            "assigned_minor": "55000",
            "supported_minor": "55000",
            "remaining_minor": "45000",
            "state": "active",
        }
        journey.assert_progress(good, 55000, 55000, 45000)
        for wrong in (
            {**good, "assigned_minor": "60000"},
            {**good, "supported_minor": "60000"},
            {**good, "remaining_minor": "40000"},
        ):
            with self.subTest(wrong=wrong), self.assertRaises(journey.Refused):
                journey.assert_progress(wrong, 55000, 55000, 45000)
        deficit = {
            "assigned_minor": "73000",
            "supported_minor": None,
            "remaining_minor": None,
            "state": "needs_review",
        }
        journey.assert_progress(deficit, 73000, None, None, "needs_review")
        with self.assertRaises(journey.Refused):
            journey.assert_progress(
                {**deficit, "supported_minor": "43000"}, 73000, None, None, "needs_review"
            )


if __name__ == "__main__":
    unittest.main()
