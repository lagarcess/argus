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

function readoutReaderInventory(overrides = new Map<string, string>()): Record<string, number> {
  const inventory: Record<string, number> = {};
  for (const path of sourceFiles(root)) {
    const file = relative(root, path);
    const source = overrides.get(file) ?? readFileSync(path, "utf8");
    const fields = new Set(["result_readout_content", "readoutContent", "resultReadoutContent"]);
    if (file === "lib/result-readout-content.ts") fields.add("text");
    const record = (node: ts.Node, expression: string) => {
      const identity = `${file}:${functionOwner(node)}:${expression}`;
      inventory[identity] = (inventory[identity] ?? 0) + 1;
    };
    for (const read of privateReads(source, fields)) record(read.node, read.expression);
    const parsed = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const visit = (node: ts.Node): void => {
      if (ts.isCallExpression(node) && ["resultReadoutContentFromMetadata", "resultReadoutText"].includes(node.expression.getText())) {
        record(node, node.expression.getText());
      }
      ts.forEachChild(node, visit);
    };
    visit(parsed);
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
      "lib/chat-message-copy-text.ts:chatMessageCopyText:message.content": 1,
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
    const mutated = source.replace("readout: resultQuickTakeText(result.readoutFacts, t, locale, result.readoutContent),",
      `readout: result.${field} || resultQuickTakeText(result.readoutFacts, t, locale, result.readoutContent),`);
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


  test("only the closed-envelope reader and its typed transports may read new prose", () => {
    expect(readoutReaderInventory()).toEqual({
      "components/chat/ChatInterface.tsx:handleStreamEvent:baseCard.readoutContent": 1,
      "components/chat/ChatInterface.tsx:handleStreamEvent:resultReadoutContentFromMetadata": 3,
      "components/chat/chat-message-projection.ts:hydrateMessagesFromApi:card.readoutContent": 1,
      "components/chat/chat-message-projection.ts:hydrateMessagesFromApi:resultReadoutContentFromMetadata": 2,
      "lib/argus-api.ts:resultCardFromConversationCard:resultReadoutContentFromMetadata": 1,
      "lib/artifact-response-transport.ts:localizeArtifactFinalPayload:resultReadoutContentFromMetadata": 2,
      "lib/chat-backtest-jobs.ts:resultMessageFromRun:baseCard.readoutContent": 1,
      "lib/chat-backtest-jobs.ts:resultMessageFromRun:resultReadoutContentFromMetadata": 1,
      "lib/chat-final-message.ts:mergeFinalTextMessage:resultReadoutContent": 1,
      "lib/chat-message-hydration.ts:hydrateTextMessageFromApi:resultReadoutContentFromMetadata": 1,
      "lib/result-card-view-model.ts:resultCardViewModel:result.readoutContent": 1,
      "lib/result-readout-content.ts:parseReadoutContent:record.text": 4,
      "lib/result-readout-content.ts:resultReadoutContentFromMetadata:record.result_readout_content": 1,
      "lib/result-readout-content.ts:resultReadoutText:readout.text": 1,
      "lib/result-readout-display.ts:resultBreakdownText:resultReadoutText": 1,
      "lib/result-readout-display.ts:resultMessageReadoutText:message.result?.readoutContent": 1,
      "lib/result-readout-display.ts:resultMessageReadoutText:message.resultReadoutContent": 2,
      "lib/result-readout-display.ts:resultQuickTakeText:resultReadoutText": 1,
    });
  });

  test.each([
    "result.result_readout_content?.text",
    "result.readoutContent?.text",
    "resultReadoutContentFromMetadata(result)?.text",
    "(() => { const { readoutContent: saved } = result; return saved?.text; })()",
  ])("detects a readout that bypasses version, language or frame validation: %s", (expression) => {
    const file = "lib/result-card-view-model.ts";
    const source = readFileSync(join(root, file), "utf8");
    const mutated = source.replace("readout: resultQuickTakeText(", `readout: ${expression} || resultQuickTakeText(`);
    expect(mutated).not.toBe(source);
    expect(readoutReaderInventory(new Map([[file, mutated]]))).not.toEqual(readoutReaderInventory());
  });

  test("every web consumer is barred from reading retained source fields", () => {
    const forbidden: string[] = [];
    for (const path of sourceFiles(root)) {
      for (const read of privateReads(readFileSync(path, "utf8"))) {
        forbidden.push(`${relative(root, path)}: ${read.expression}`);
      }
    }
    expect(forbidden).toEqual([]);
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
