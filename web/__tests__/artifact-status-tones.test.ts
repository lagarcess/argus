import { describe, expect, test } from "bun:test";

import {
  artifactLifecycleTone,
  artifactStatusToneClassName,
} from "../lib/artifact-status-tones";

describe("artifact status tones", () => {
  test("separates lifecycle state from investment outcome color", () => {
    expect(artifactLifecycleTone("ready_to_run")).toBe("info");
    expect(artifactLifecycleTone("queued")).toBe("info");
    expect(artifactLifecycleTone("running")).toBe("info");
    expect(artifactLifecycleTone("request_sent")).toBe("info");

    expect(artifactLifecycleTone("run_complete")).toBe("neutral");
    expect(artifactLifecycleTone("simulation_complete")).toBe("neutral");
    expect(artifactLifecycleTone("result_ready")).toBe("neutral");
    expect(artifactLifecycleTone("not_completed")).toBe("neutral");
    expect(artifactLifecycleTone("canceled")).toBe("neutral");
    expect(artifactLifecycleTone("expired")).toBe("neutral");

    expect(artifactLifecycleTone("could_not_run")).toBe("danger");
    expect(artifactLifecycleTone("failed")).toBe("danger");
    expect(artifactLifecycleTone("saved")).toBe("success");
  });

  test("keeps status tone classes muted and tokenized", () => {
    expect(artifactStatusToneClassName("info")).toContain("#7da0ca");
    expect(artifactStatusToneClassName("danger")).toContain("#d66d75");
    expect(artifactStatusToneClassName("neutral")).toContain("border-black/10");
    expect(artifactStatusToneClassName("success")).toContain("#70a38d");
  });
});
