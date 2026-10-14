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
