import { afterEach, describe, expect, test } from "bun:test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { previewCodeIdentity } from "../e2e/ecosystem-preview-evidence";

const repositories: string[] = [];
const inputs = [
  "web/app/dev/ecosystem/page.tsx",
  "web/e2e/ecosystem-preview.spec.ts",
  "web/e2e/ecosystem-preview.support.ts",
  "web/e2e/ecosystem-preview.playwright.config.ts",
  "web/components/ui/AdaptivePanel.tsx",
  "web/package.json",
  "root-config.json",
];

function write(root: string, filename: string, content: string) {
  const target = path.join(root, filename);
  mkdirSync(path.dirname(target), { recursive: true });
  writeFileSync(target, content);
}

function repository() {
  const root = mkdtempSync(path.join(os.tmpdir(), "argus-evidence-"));
  repositories.push(root);
  const git = (...args: string[]) => execFileSync("git", args, { cwd: root, encoding: "utf8", stdio: "pipe" }).trim();
  git("init", "--quiet");
  inputs.forEach((filename) => write(root, filename, "committed input\n"));
  write(root, "docs/reports/evidence/preview/existing.json", "{}\n");
  git("add", ".");
  git("-c", "user.name=Evidence Test", "-c", "user.email=evidence@example.invalid", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "test fixture");
  return { root, git, output: path.join(root, "docs/reports/evidence/preview") };
}

afterEach(() => repositories.splice(0).forEach((root) => rmSync(root, { recursive: true, force: true })));

describe("durable preview evidence provenance", () => {
  test("records the committed head while allowing only its generated evidence files", () => {
    const { root, output, git } = repository();
    write(root, "docs/reports/evidence/preview/existing.json", "{\"updated\": true}\n");
    write(root, "docs/reports/evidence/preview/interactions/new.json", "{}\n");
    expect(previewCodeIdentity(root, output)).toEqual({ codeHead: git("rev-parse", "HEAD"), worktreeChanges: "" });
  });

  test.each(inputs)("rejects an uncommitted evidence input: %s", (filename) => {
    const { root, output } = repository();
    write(root, filename, "uncommitted behavior\n");
    expect(() => previewCodeIdentity(root, output)).toThrow("Commit all code and test inputs");
  });

  test.each(["web/e2e/new-helper.ts", "docs/reports/evidence/another-run/record.json"])("rejects an untracked or staged file outside this run's output: %s", (filename) => {
    const { root, output, git } = repository();
    write(root, filename, "uncommitted\n");
    expect(() => previewCodeIdentity(root, output)).toThrow("Commit all code and test inputs");
    git("add", filename);
    expect(() => previewCodeIdentity(root, output)).toThrow("Commit all code and test inputs");
  });

  test("cannot hide dirty source files by selecting a source directory as evidence output", () => {
    const { root } = repository();
    write(root, inputs[0], "uncommitted behavior\n");
    for (const output of [root, path.join(root, "web"), path.join(root, "docs/reports/evidence")]) {
      expect(() => previewCodeIdentity(root, output)).toThrow("a run directory under docs/reports/evidence");
    }
  });

  test("checks the entire worktree for external output and reports dirty exploratory captures", () => {
    const { root } = repository();
    write(root, inputs[1], "uncommitted test\n");
    expect(() => previewCodeIdentity(root, path.join(os.tmpdir(), "external-preview-output"))).toThrow("Commit all code and test inputs");
    expect(previewCodeIdentity(root).worktreeChanges).toContain(inputs[1]);
  });
});
