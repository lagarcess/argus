import { describe, expect, test } from "bun:test";
import {
  quietNoticeContainerClass,
  retryableNoticeContainerClass,
} from "../lib/failure-treatment";
import {
  alreadyUpToDateText,
  decisionRerunTreatment,
  toolOutcomeTreatment,
} from "../lib/tool-outcome-treatment";
import type { ToolOutcome } from "../lib/tool-result-card";
import { translate } from "./support/i18n-instance";

const failed = (status: ToolOutcome["status"], code: string, fields: string[] = []): ToolOutcome => ({
  status,
  result: null,
  failure: { code, fields },
});

describe("the one owner mapping tool outcomes onto the shared failure treatments", () => {
  test("an outage is the retryable amber notice; the inputs' failures are the quiet notice", async () => {
    const instance = await translate("en");
    const t = instance.t.bind(instance);
    const outage = toolOutcomeTreatment(failed("unavailable", "tool_execution_failed"), t);
    expect(outage?.tone).toBe("retryable");
    expect(outage?.classes.container).toBe(retryableNoticeContainerClass);
    expect(outage?.classes.retryPill).not.toBeNull();
    expect(outage?.message).toBe("This result is unavailable right now.");
    for (const status of ["invalid", "ambiguous", "bounded"] as const) {
      const quiet = toolOutcomeTreatment(failed(status, "unmapped_code", ["rate"]), t, (name) => name);
      expect(quiet?.tone).toBe("quiet");
      expect(quiet?.classes.container).toBe(quietNoticeContainerClass);
      expect(quiet?.classes.retryPill).toBeNull();
      // An unmapped code falls back to the status copy, never to a raw key.
      expect(quiet?.message).not.toContain("tools.card");
    }
    expect(toolOutcomeTreatment({ status: "succeeded", result: {}, failure: null }, t)).toBeNull();
  });

  test("codes name their field in both languages", async () => {
    const en = await translate("en");
    const es = await translate("es-419");
    const outcome = failed("invalid", "division_by_zero", ["per_share"]);
    expect(toolOutcomeTreatment(outcome, en.t.bind(en), () => "Per share")?.message).toBe("The Per share cannot be zero here.");
    expect(toolOutcomeTreatment(outcome, es.t.bind(es), () => "Por acción")?.message).toBe("El dato Por acción no puede ser cero aquí.");
  });

  test("decision re-run reasons keep the existing codes and stay quiet", async () => {
    const instance = await translate("en");
    const t = instance.t.bind(instance);
    for (const code of ["kernel_unavailable", "invalid_inputs", "inputs_not_editable", "run_unavailable", "retest_unavailable"] as const) {
      const treatment = decisionRerunTreatment(code, t);
      expect(treatment.tone).toBe("quiet");
      expect(treatment.message).not.toContain("tools.decision");
      expect(treatment.repair).toBeNull();
    }
    expect(alreadyUpToDateText(t)).toBe("Already up to date");
  });
});
