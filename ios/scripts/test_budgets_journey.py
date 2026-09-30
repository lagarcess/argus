"""Offline checks for safe connected budget acceptance and crash replay."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("budgets_journey", Path(__file__).with_name("budgets-journey.py"))
journey = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(journey)


class JourneyTests(unittest.TestCase):
    def test_rejects_external_or_unrelated_route_before_authentication(self):
        client = journey.Client({})
        with patch.object(client, "login") as login:
            for path in ("https://example.test/financial-plan", "/auth/login", "/financial-plan/../auth", "//example.test/financial-plan"):
                with self.subTest(path=path), self.assertRaises(journey.scene.Refused):
                    client.api(0, "POST", path)
            login.assert_not_called()

    def test_crash_replays_original_bytes_and_key_before_changing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            target = work / "private.json"
            with patch.object(journey.scene, "WORK", work), patch.object(journey.scene, "STATE", target):
                state = journey.scene.load_state(create=True)
                calls = []

                def lost_then_accepted(client, method, path, body, key, statuses):
                    saved = json.loads(target.read_text())["operations"]["budget"]
                    self.assertEqual(saved["body"].encode(), body)
                    self.assertEqual(saved["key"], key)
                    calls.append((method, path, body, key))
                    if len(calls) == 1:
                        raise journey.scene.Refused("response lost")
                    return {"budget": {"id": "budget-one"}, "replayed": True}

                with patch.object(journey.scene, "expect", side_effect=lost_then_accepted):
                    with self.assertRaises(journey.scene.Refused):
                        journey.write(None, state, "budget", "POST", "/financial-plan/budgets", {"limit": "150"})
                    restored = journey.scene.load_state(create=False)
                    journey.write(None, restored, "budget", "POST", "/financial-plan/budgets", {"limit": "999"})
                self.assertEqual(calls[0], calls[1])
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                self.assertEqual(restored["operations"]["budget"]["result"]["budget"]["id"], "budget-one")

    def test_proxy_drops_accepted_response_then_replays_same_command(self):
        client = journey.Client({}, response_loss=True)
        client.sessions[0] = {"access_token": "synthetic-token"}
        calls = []

        def request(url, method, body, headers):
            if url.endswith("/__fault"):
                return 200, {"armed": method == "POST", "dropped": 0 if method == "POST" else 1}
            calls.append((url, method, body, headers))
            if len(calls) == 1:
                raise journey.scene.Refused("Local HTTP request failed; rerun setup to replay pending write")
            return 201, {"budget": {"id": "budget-one"}, "replayed": True}

        with patch.object(client, "raw", side_effect=request):
            status, result = client.api(0, "POST", "/financial-plan/budgets", b'{"limit":"150"}', "same-key")
        self.assertEqual(status, 201)
        self.assertTrue(result["replayed"])
        self.assertEqual(calls[0], calls[1])
        self.assertTrue(client.response_loss_verified)

    def test_independent_total_detects_incorrect_calculation(self):
        with patch.object(journey.scene, "expect", return_value={
            "spent_minor": "15000", "remaining_minor": "1000", "over_budget_minor": "0"}):
            with self.assertRaisesRegex(journey.scene.Refused, "independent expected totals"):
                journey.progress(None, "budget-one", (15500, 500, 0))


if __name__ == "__main__":
    unittest.main()
