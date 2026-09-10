"""Offline checks for the paid browser harness. No network or Argus imports."""
import asyncio
import json
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
import requests

from budget import Budget, install_http_budget


PAYLOAD = {"model": "openai/gpt-oss-120b", "max_tokens": 2400, "messages": [{"role": "user", "content": "A local fixture"}], "response_format": {"json_schema": {"name": "ResultBreakdownDraft"}}}


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.budget = Budget(Path(self.tmp.name) / "ledger.json")

    def test_http400_charges_full_reservation_and_leaves_normal_retry_available(self):
        index = self.budget.reserve(PAYLOAD)
        with patch.dict(os.environ, {"QA_API_KEY": "private-fixture-key"}):
            self.budget.finish(index, {"error": {"code": 400, "message": "Provider returned error", "metadata": {"raw": "Unsupported setting private-fixture-key", "provider_name": "fixture"}}}, 400)
        row = self.budget.attempts[0]
        self.assertIsNone(row["cost_usd"])
        self.assertEqual(row["accounted_cost_usd"], row["reservation_usd"])
        self.assertEqual(row["provider_error"]["metadata"]["raw"], "Unsupported setting [REDACTED]")
        self.assertIsNone(self.budget.halted)
        second = self.budget.reserve(PAYLOAD)
        self.budget.finish(second, {"usage": {"cost": .0001}}, 200)
        self.assertEqual(Decimal(self.budget.summary()["accounted_cost_usd"]), Decimal(row["reservation_usd"]) + Decimal(".0001"))

    def test_async_cancellation_is_charged_and_reraised(self):
        async def canceled(*args, **kwargs):
            raise asyncio.CancelledError()
        originals = (httpx.Client.send, httpx.AsyncClient.send, requests.Session.request)
        try:
            httpx.AsyncClient.send = canceled
            install_http_budget(self.budget, [])
            async def run():
                async with httpx.AsyncClient() as client:
                    await client.post("https://openrouter.ai/api/v1/chat/completions", json=PAYLOAD)
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(run())
        finally:
            httpx.Client.send, httpx.AsyncClient.send, requests.Session.request = originals
        row = self.budget.attempts[0]
        self.assertEqual(row["error_class"], "CancelledError")
        self.assertEqual(row["cost_basis"], "full_reservation")
        self.assertIsNone(self.budget.halted)

    def test_resume_preserves_observed_fields_and_limits_four_total_runs(self):
        ledger = json.loads((Path(__file__).parent / "initial-c36/fee-ledger.json").read_text())
        environment = json.loads((Path(__file__).parent / "initial-c36/environment.json").read_text())
        self.budget.restore(ledger, environment["run_attempts"], environment["candidate_sha"])
        self.assertEqual(self.budget.summary()["accounted_cost_usd"], "0.06765977")
        self.assertEqual(self.budget.summary()["remaining_usd"], "0.93234023")
        for old, current in zip(ledger["attempts"], self.budget.attempts):
            for key, value in old.items():
                self.assertEqual(current[key], value)
        self.budget.case = "docn-en"
        with self.assertRaises(RuntimeError):
            self.budget.reserve_backtest({})
        for case in ["docn-es", "dca-costs", "indicator"]:
            self.budget.case = case
            self.budget.finish_backtest(self.budget.reserve_backtest({}), True)
        self.budget.case = "fifth"
        with self.assertRaises(RuntimeError):
            self.budget.reserve_backtest({})
        self.assertEqual(len(self.budget.backtest_attempts), 4)

    def test_unpriced_model_and_insufficient_reservation_stop_before_attempt(self):
        for payload, cap in [({**PAYLOAD, "model": "unknown"}, "1"), (PAYLOAD, ".00001")]:
            budget = Budget(Path(self.tmp.name) / "blocked.json", cap)
            with self.assertRaises(RuntimeError):
                budget.reserve(payload)
            self.assertEqual(budget.attempts, [])
            self.assertIsNotNone(budget.halted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
