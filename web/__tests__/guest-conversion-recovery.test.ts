import { expect, test } from "bun:test";
import path from "node:path";
import ts from "typescript";
import type { ChatFinalPayload } from "../lib/argus-api";
import { isGuestSimulationConversionRejection } from "../lib/guest-conversion-recovery";

test("recognizes only authoritative guest run conversion rejections", () => {
  expect(
    isGuestSimulationConversionRejection("account_conversion_required", {
      type: "run_backtest",
      id: "run",
      label: "Run",
      value: "run",
    }),
  ).toBe(true);
  expect(
    isGuestSimulationConversionRejection("account_conversion_required", undefined),
  ).toBe(false);
});

const conversionCode = "account_conversion_required";
const finalPayloadCases: Array<{
  label: string;
  payload: ChatFinalPayload;
  converts: boolean;
}> = [
  {
    label: "nested final response",
    payload: { final_response_payload: { code: conversionCode } },
    converts: true,
  },
  {
    label: "legacy top-level code",
    payload: { final_response_payload: null, code: conversionCode },
    converts: true,
  },
  { label: "legacy payload without a code", payload: {}, converts: false },
];

test.each(finalPayloadCases)("reads the typed $label", ({ payload, converts }) => {
  expect(
    isGuestSimulationConversionRejection(
      payload.final_response_payload?.code ?? payload.code,
      { type: "run_backtest", id: "run", label: "Run", value: "run" },
    ),
  ).toBe(converts);
});

test("canonical stream types compile a guest conversion consumer", () => {
  const webRoot = path.resolve(import.meta.dir, "..");
  const probePath = path.join(webRoot, "guest-conversion-type-probe.ts");
  const source = `
    import type { ChatFinalPayload } from "./lib/argus-api";
    const payloads: ChatFinalPayload[] = [
      { final_response_payload: { code: "account_conversion_required" } },
      { final_response_payload: { code: null } },
      { final_response_payload: null },
      {},
    ];
    for (const payload of payloads) {
      const code: string | null | undefined =
        payload.final_response_payload?.code ?? payload.code;
      void code;
    }
  `;
  const config = ts.readConfigFile(path.join(webRoot, "tsconfig.json"), ts.sys.readFile);
  const { options } = ts.parseJsonConfigFileContent(config.config, ts.sys, webRoot);
  const host = ts.createCompilerHost(options);
  const getSourceFile = host.getSourceFile.bind(host);
  host.getSourceFile = (fileName, languageVersion, onError, shouldCreateNewSourceFile) =>
    fileName === probePath
      ? ts.createSourceFile(fileName, source, languageVersion, true)
      : getSourceFile(fileName, languageVersion, onError, shouldCreateNewSourceFile);
  const program = ts.createProgram([probePath], options, host);
  const probe = program.getSourceFile(probePath);
  expect(probe).toBeDefined();
  // Check this consumer independently of the repo's legacy Bun test typings.
  const diagnostics = program.getSemanticDiagnostics(probe);
  expect(diagnostics.map((item) => ts.flattenDiagnosticMessageText(item.messageText, "\n")))
    .toEqual([]);
});
