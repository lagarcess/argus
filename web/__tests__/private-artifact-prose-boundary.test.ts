import { describe, expect, test } from "bun:test";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import ts from "typescript";
import privateFields from "../../src/argus/domain/artifact_prose_fields.json";
import rootProseFields from "../../src/argus/domain/artifact_root_prose_fields.json";

const privateKeys = new Set(privateFields);
const root = join(import.meta.dir, "..");

function privateReads(source: string, fields = privateKeys): Array<{ key: string; expression: string; node: ts.Node }> {
  const file = ts.createSourceFile("surface.tsx", source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const aliases = new Map<string, string>();
  const reads: Array<{ key: string; expression: string; node: ts.Node }> = [];
  const literal = (node: ts.Node | undefined): string | undefined => node && ts.isStringLiteralLike(node)
    ? node.text : node && ts.isIdentifier(node) ? aliases.get(node.text) : undefined;
  function visit(node: ts.Node): void {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
      const value = literal(node.initializer);
      if (value) aliases.set(node.name.text, value);
    }
    const key = ts.isPropertyAccessExpression(node) ? node.name.text
      : ts.isElementAccessExpression(node) ? literal(node.argumentExpression)
      : ts.isBindingElement(node) ? (node.propertyName?.getText(file).replace(/["']/g, "") ?? node.name.getText(file))
      : undefined;
    if (key && fields.has(key)) reads.push({ key, expression: node.getText(file), node });
    ts.forEachChild(node, visit);
  }
  visit(file);
  return reads;
}

function functionOwner(node: ts.Node): string {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (ts.isFunctionDeclaration(parent) && parent.name) return parent.name.text;
    if ((ts.isArrowFunction(parent) || ts.isFunctionExpression(parent))
      && ts.isVariableDeclaration(parent.parent)) return parent.parent.name.getText();
  }
  return "<module>";
}

function rootReaderInventory(overrides = new Map<string, string>()): Record<string, number> {
  const inventory: Record<string, number> = {};
  for (const path of sourceFiles(root)) {
    const file = relative(root, path);
    // Artifact presentation and its common transcript adapter own this
    // boundary. New result/artifact helpers are covered by construction.
    if (!/(?:^|\/)(?:artifact-|result-|confirmation-|conversation-preview|chat-message-|chat-card-copy-|ChatMessage\.|RunDossierView\.)/.test(file)) continue;
    for (const read of privateReads(overrides.get(file) ?? readFileSync(path, "utf8"), new Set(rootProseFields))) {
      const identity = `${file}:${functionOwner(read.node)}:${read.expression}`;
      inventory[identity] = (inventory[identity] ?? 0) + 1;
    }
  }
  return inventory;
}

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (entry.name.startsWith(".") || ["node_modules", "__tests__", "e2e", "public", "test-results", "playwright-report"].includes(entry.name)) return [];
    const path = join(directory, entry.name);
    return entry.isDirectory() ? sourceFiles(path) : /\.tsx?$/.test(path) ? [path] : [];
  });
}

describe("private artifact prose AST boundary", () => {
  test("retained root prose has only exact generic transcript readers", () => {
    expect(rootReaderInventory()).toEqual({
      // These props already contain boundary-localized output, not source prose.
      "components/chat/ChatMessage.tsx:ResultBreakdown:content": 1,
      "components/chat/ChatMessage.tsx:ResultReadout:content": 1,
      "components/chat/ChatMessage.tsx:UserMessageContent:content": 1,
      // Generic text fallthrough after every typed artifact returns. Counts
      // are exact: adding a raw-text fallback inside an artifact branch fails.
      "components/chat/ChatMessage.tsx:getCopyText:message.content": 1,
      "components/chat/ChatMessage.tsx:getDisplayContent:message.content": 1,
      // General transcript hydration/stream state consumes the scrubbed DTO.
      "components/chat/chat-message-projection.ts:applyEmptyFinalFallback:options.content": 1,
      "components/chat/chat-message-projection.ts:hydrateMessagesFromApi:message.content": 1,
      "components/chat/chat-message-projection.ts:messageStreamPresentation:message.content": 1,
      "lib/chat-message-hydration.ts:hydrateTextMessageFromApi:message.content": 1,
      "lib/chat-message-hydration.ts:hydrateTextMessageFromApi:options.retryRequestMessage.content": 1,
      "lib/chat-message-hydration.ts:precedingUserMessageForRetryableRecovery:candidate.content": 1,
      "lib/chat-message-hydration.ts:retryActionsFromMetadata:message.content": 1,
      "lib/chat-message-hydration.ts:retryActionsFromMetadata:retryRequestMessage?.content": 1,
    });
  });

  test.each(rootProseFields)("detects a real artifact-template fallback mutation: %s", (field) => {
    const file = "lib/result-card-view-model.ts";
    const source = readFileSync(join(root, file), "utf8");
    const mutated = source.replace("readout: resultQuickTakeText(result.readoutFacts, t, locale),",
      `readout: result.${field} || resultQuickTakeText(result.readoutFacts, t, locale),`);
    expect(mutated).not.toBe(source);
    expect(rootReaderInventory(new Map([[file, mutated]]))).not.toEqual(rootReaderInventory());
  });

  test.each([
    "return <p>{card.quick_take}</p>",
    "return card['breakdown'] || fallback",
    "const { result_readout: saved } = response; return saved",
    "const key = 'quick_take'; return card[key]",
    "return <p>{record.audit_context?.text}</p>",
  ])("rejects a new template or compatibility fallback: %s", (source) => {
    expect(privateReads(`function template(card, response, record, fallback) { ${source} }`).length).toBeGreaterThan(0);
  });

  test("every web consumer is barred from reading retained source fields", () => {
    const forbidden: string[] = [];
    let reservedNullReads = 0;
    for (const path of sourceFiles(root)) {
      for (const read of privateReads(readFileSync(path, "utf8"))) {
        // Founder-reserved #543 file. Its one existing argument is inert:
        // the public DTO is null-only and backend serialization tests enforce it.
        const call = read.node.parent;
        if (relative(root, path) === "lib/chat-backtest-jobs.ts" && read.expression === "response.result_readout"
          && ts.isCallExpression(call) && call.expression.getText() === "resultMessageFromRun" && call.arguments[2] === read.node) {
          reservedNullReads += 1;
        } else forbidden.push(`${relative(root, path)}: ${read.expression}`);
      }
    }
    expect(forbidden).toEqual([]);
    expect(reservedNullReads).toBe(1);
    const api = ts.createSourceFile("api.ts", readFileSync(join(root, "lib/argus-api.ts"), "utf8"), ts.ScriptTarget.Latest, true);
    let nullOnly = false;
    function verify(node: ts.Node): void {
      if (ts.isPropertySignature(node) && node.name.getText() === "result_readout") nullOnly = node.type?.getText() === "null";
      ts.forEachChild(node, verify);
    }
    verify(api);
    expect(nullOnly).toBe(true);
  });
});
