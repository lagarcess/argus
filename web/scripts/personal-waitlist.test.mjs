import assert from "node:assert/strict";
import test from "node:test";
import { POST } from "../app/api/personal-waitlist/route.ts";

test("signup stays unavailable and never confirms a saved registration", async () => {
  const response = POST();

  assert.equal(response.status, 503);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.deepEqual(await response.json(), { error: "unavailable" });
});
