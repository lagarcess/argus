import { test } from "bun:test";
import assert from "node:assert/strict";
import { chatActionRequestFromAction } from "../components/chat/chat-message-projection";

test("retired Run and Retest cannot become transport requests", () => {
  for (const type of ["run_backtest", "retest_run"] as const) {
    assert.throws(() => chatActionRequestFromAction({ type, label: "Stored action" }), TypeError);
  }
});

test("supported actions preserve their label, payload and ownership", () => {
  const action = { type: "cancel_confirmation", label: "Cancel", payload: { confirmation_id: "c1" } } as const;
  assert.deepEqual(chatActionRequestFromAction(action), {
    ...action, labelKey: undefined, presentation: undefined,
  });
});

test("retired client exports are absent while shared job reads remain", async () => {
  const api = await import("../lib/argus-api");
  const reconciliation = await import("../lib/chat-run-reconciliation");
  assert.equal("runBacktest" in api, false);
  assert.equal("getBacktestRun" in api, false);
  assert.equal("getBacktestJobByAction" in reconciliation, false);
  assert.equal(typeof api.getBacktestJob, "function");
});
