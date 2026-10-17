import { execFileSync } from "node:child_process";
import path from "node:path";

export function previewCodeIdentity(repositoryRoot: string, evidenceDir?: string) {
  const paths = ["."];
  if (evidenceDir) {
    const relativeOutput = path.relative(repositoryRoot, path.resolve(evidenceDir));
    const outsideRepository = relativeOutput === ".." || relativeOutput.startsWith(`..${path.sep}`) || path.isAbsolute(relativeOutput);
    if (!outsideRepository) {
      const evidenceRoot = path.join("docs", "reports", "evidence");
      if (!relativeOutput.startsWith(`${evidenceRoot}${path.sep}`)) {
        throw new Error("Durable evidence inside the repository must use a run directory under docs/reports/evidence.");
      }
      // Captures make their own output dirty. Only that run's artifacts are
      // excluded; source, shared components, tests and configuration all count.
      paths.push(`:(top,literal,exclude)${relativeOutput.split(path.sep).join("/")}`);
    }
  }
  const git = (...args: string[]) => execFileSync("git", args, { cwd: repositoryRoot, encoding: "utf8" }).trim();
  const worktreeChanges = git("status", "--porcelain", "--untracked-files=all", "--", ...paths);
  if (evidenceDir && worktreeChanges) {
    throw new Error(`Commit all code and test inputs before recording durable exact-head evidence.\n${worktreeChanges}`);
  }
  return { codeHead: git("rev-parse", "HEAD"), worktreeChanges };
}
