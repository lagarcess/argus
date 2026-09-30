"""Offline safety checks for the allocation-59000 fixture CLI."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PATH = Path(__file__).with_name("budgets-acceptance.py")
SPEC = importlib.util.spec_from_file_location("budgets_acceptance", PATH)
script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(script)


class BudgetAcceptanceTests(unittest.TestCase):
    def test_rejects_other_endpoint_before_login(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Path(directory) / "client.json"
            client.write_text(json.dumps({"apiURL": "http://127.0.0.1:58700/api/v1",
                                          "supabaseURL": script.AUTH,
                                          "publicAnonKey": "local", "users": [{}, {}]}))
            with patch.object(script, "CLIENT", client):
                with self.assertRaisesRegex(script.Refused, "endpoints"):
                    script.load_client()

    def test_pending_bytes_and_key_survive_lost_response(self):
        class LostThenReplayed:
            def __init__(self, private_state):
                self.calls = []
                self.private_state = private_state

            def api(self, owner, method, path, body, key):
                persisted = json.loads(self.private_state.read_text())
                self.calls.append((body, key))
                assert persisted["pending"]["body"].encode() == body
                assert persisted["pending"]["key"] == key
                if len(self.calls) == 1:
                    raise script.Refused("response lost")
                return 200, {"id": "00000000-0000-0000-0000-000000000001"}

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            state_path = work / "private.json"
            with patch.object(script, "WORK", work), patch.object(script, "STATE", state_path):
                state = script.load_state(create=True)
                client = LostThenReplayed(state_path)
                body = script.wire(script.account_request("checking", state))
                with self.assertRaisesRegex(script.Refused, "response lost"):
                    script.pending_write(client, state, "account", "checking",
                                         "/financial-accounts", body)
                restored = script.load_state(create=False)
                script.pending_write(client, restored, "account", "checking",
                                     "/financial-accounts", body)
                self.assertEqual(client.calls[0], client.calls[1])
                self.assertEqual(restored["accounts"]["checking"],
                                 "00000000-0000-0000-0000-000000000001")
                self.assertIsNone(json.loads(state_path.read_text())["pending"])
                self.assertEqual(state_path.stat().st_mode & 0o777, 0o600)

    def test_readback_has_no_write_route(self):
        class ReadOnlyClient:
            def __init__(self, state):
                self.state = state
                self.calls = []

            def api(self, owner, method, path, body=None, key=None):
                assert method == "GET" and body is None and key is None
                self.calls.append((owner, path))
                if owner == 1:
                    return 404, {"code": "financial_account_not_found"}
                for label, _, currency, opening, balance in script.ACCOUNTS:
                    if path.endswith(self.state["accounts"][label]):
                        return 200, {
                            "id": self.state["accounts"][label], "currency": currency,
                            "nickname": f"Budget demo {label} fixed",
                            "balance": {"state": "unknown" if balance is None else "known",
                                        "amount_minor": balance,
                                        "activity_since_tracking_minor": -300 if balance is None else 0},
                            "opening": None if opening is None else {
                                "amount_minor": int(opening.replace(".", ""))},
                        }
                for row in script.ACTIVITIES:
                    label, kind, amount, currency, category, names, movements = row
                    if path.endswith(self.state["activities"][label]):
                        return 200, {
                            "activity_id": self.state["activities"][label],
                            "kind": kind, "currency": currency,
                            "amount_minor": int(amount.replace(".", "")),
                            "category_id": category, "note": f"Budget demo {label} fixed",
                            "time_zone": script.ZONE,
                            "legs": [{"account_id": self.state["accounts"][name],
                                      "balance_movement_minor": move}
                                     for name, move in zip(names, movements, strict=True)],
                        }
                raise AssertionError("Unexpected readback route")

        state = {"pending": None, "suffix": "fixed",
                 "accounts": {row[0]: f"account-{index}" for index, row in enumerate(script.ACCOUNTS)},
                 "activities": {row[0]: f"activity-{index}" for index, row in enumerate(script.ACTIVITIES)},
                 "replay_proof": {"account_checked": True, "activity_checked": True}}
        client = ReadOnlyClient(state)
        snapshot = script.readback(client, state)
        self.assertEqual(snapshot["accounts"]["checking"], 82300)
        self.assertEqual(snapshot["accounts"]["unknown"], "unknown")
        self.assertEqual(len(client.calls), 15)


if __name__ == "__main__":
    unittest.main()
