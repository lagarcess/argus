// Operator tool for Cuadrao early-access signups.
//   bun run scripts/signups.ts summary
//   bun run scripts/signups.ts remove someone@example.com
//   bun run scripts/signups.ts notice --template notice.json            (dry run)
//   bun run scripts/signups.ts notice --template notice.json --only a@x.com,b@y.com --send
//   bun run scripts/signups.ts notice --template notice.json --send --expect 42
// Needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY; notice also needs
// RESEND_API_KEY and CUADRAO_NOTICE_FROM. Nothing here prints an address.
import { readFileSync } from "node:fs";
import { readFormsConfig } from "../lib/forms/config";
import {
  pendingSignups,
  planNotice,
  removeSignup,
  sendNotice,
  signupCounts,
  validateTemplate,
  type NoticeTemplate,
  type OpsConfig,
} from "../lib/ops/signups";

function option(args: string[], name: string): string | null {
  const index = args.indexOf(`--${name}`);
  return index >= 0 ? (args[index + 1] ?? null) : null;
}

function fail(message: string): never {
  console.error(message);
  process.exit(1);
}

const [command, ...args] = process.argv.slice(2);
const config: OpsConfig = {
  ...readFormsConfig(process.env),
  noticeFrom: process.env.CUADRAO_NOTICE_FROM?.trim() || null,
};
if (!config.supabaseUrl || !config.supabaseServiceKey) {
  fail("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.");
}

if (command === "summary") {
  console.log(JSON.stringify(await signupCounts(config, fetch)));
} else if (command === "remove") {
  const email = args[0];
  if (!email) fail("Usage: remove <email>");
  console.log(`Signup ${await removeSignup(config, email, fetch)}.`);
} else if (command === "notice") {
  const path = option(args, "template");
  if (!path) fail("--template <file.json> is required.");
  const template = JSON.parse(readFileSync(path, "utf8")) as NoticeTemplate;
  const problems = validateTemplate(template);
  if (problems.length) fail(`Template problems:\n- ${problems.join("\n- ")}`);
  const only = option(args, "only")?.split(",").map((value) => value.trim()).filter(Boolean) ?? null;
  const plan = planNotice(await pendingSignups(config, fetch), only);
  const byLanguage = { es: 0, en: 0 };
  for (const row of plan.recipients) byLanguage[row.language] += 1;
  console.log(
    JSON.stringify({ template: template.id, recipients: plan.recipients.length, byLanguage, stamps: plan.stamp }),
  );
  if (!args.includes("--send")) {
    console.log("Dry run. Nothing was sent. Add --send to send.");
  } else {
    const expected = option(args, "expect");
    if (!only && Number(expected) !== plan.recipients.length) {
      fail(`A full send needs --expect ${plan.recipients.length} to confirm the recipient count.`);
    }
    if (!config.resendApiKey || !config.noticeFrom) fail("RESEND_API_KEY and CUADRAO_NOTICE_FROM are required to send.");
    console.log(JSON.stringify(await sendNotice(config, template, plan, fetch)));
  }
} else {
  fail("Commands: summary | remove <email> | notice --template <file> [--only a,b] [--send] [--expect N]");
}
