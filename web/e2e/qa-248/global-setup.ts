import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

// Fail-closed gate for every real-auth QA run: no browser starts unless the
// configured targets are provably non-production and the harness is healthy.
export default async function globalSetup() {
  const root = path.resolve(__dirname, "../../..");
  execFileSync("bash", [path.join(root, "scripts/qa/assert-nonprod-target.sh")], {
    stdio: "inherit",
    env: process.env,
  });

  if (!existsSync(path.join(root, ".qa-identities.env"))) {
    throw new Error(
      ".qa-identities.env missing — run scripts/qa/setup-local-identities.sh first",
    );
  }

  const api = process.env.QA_ARGUS_API ?? "http://127.0.0.1:8000/api/v1";
  const probe = await fetch(`${api}/auth/session`).catch(() => null);
  if (!probe || (probe.status !== 200 && probe.status !== 401)) {
    throw new Error(`Argus API not healthy at ${api} (status ${probe?.status ?? "unreachable"})`);
  }

  const hostedMode = Boolean(process.env.ARGUS_QA_APPROVED_SUPABASE_REF);
  if (!hostedMode) {
    const mailpit = process.env.QA_MAILPIT_URL ?? "http://127.0.0.1:54334";
    const mail = await fetch(`${mailpit}/api/v1/messages?limit=1`).catch(() => null);
    if (!mail || !mail.ok) {
      throw new Error(`Mailpit not reachable at ${mailpit} — local recovery QA needs it`);
    }
  }
}
