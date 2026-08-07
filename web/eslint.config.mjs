import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Flat config REPLACES a rule's options rather than merging them, so every
// file that needs any of these selectors must receive all of them in a single
// no-restricted-syntax entry. Splitting them across config objects silently
// disables the earlier set.
const STORAGE_SELECTORS = [
  {
    selector: "MemberExpression[property.name=/^(localStorage|sessionStorage)$/]",
    message:
      "Use lib/browser-storage.ts. Its registry is what the privacy policy discloses.",
  },
  {
    selector: "Identifier[name=/^(localStorage|sessionStorage)$/]",
    message:
      "Use lib/browser-storage.ts. Its registry is what the privacy policy discloses.",
  },
  {
    selector: "MemberExpression[object.name='document'][property.name='cookie']",
    message:
      "Cookies are written by the backend chokepoint or the gated Supabase adapter, never from page code.",
  },
];

/**
 * Cookie WRITES only, alias-aware.
 *
 * A selector cannot see that `const store = await cookies()` makes `store` a
 * cookie store, so the ordinary Next.js form slipped past pure selectors. The
 * obvious patch is to ban the `next/headers` import, which is what an earlier
 * revision did, but that blocks *reading* cookies to prevent *writing* them:
 * rigidity charged against ordinary work to catch a rare mistake.
 *
 * This tracks the binding instead. It reports `.set`/`.delete` on anything
 * known to be a cookie store, however that store was reached, and says nothing
 * about reads.
 */
const MESSAGE =
  "Cookie writes belong in lib/supabase-server.ts, the one adapter the disclosure covers. Reading cookies anywhere is fine.";

const noUnroutedCookieWrite = {
  meta: {
    type: "problem",
    schema: [],
    messages: { write: MESSAGE },
  },
  create(context) {
    const stores = new Set();

    const unwrap = (node) =>
      node && node.type === "AwaitExpression" ? node.argument : node;

    // `cookies()` from next/headers, or any `.cookies` accessor such as
    // NextResponse.cookies / response.cookies.
    const isCookieStore = (node) => {
      const value = unwrap(node);
      if (!value) return false;
      if (
        value.type === "CallExpression" &&
        value.callee.type === "Identifier" &&
        value.callee.name === "cookies"
      ) {
        return true;
      }
      return (
        value.type === "MemberExpression" &&
        value.property.type === "Identifier" &&
        value.property.name === "cookies"
      );
    };

    return {
      VariableDeclarator(node) {
        if (node.id.type === "Identifier" && isCookieStore(node.init)) {
          stores.add(node.id.name);
        }
      },
      AssignmentExpression(node) {
        if (node.left.type === "Identifier" && isCookieStore(node.right)) {
          stores.add(node.left.name);
        }
      },
      "CallExpression > MemberExpression"(node) {
        if (
          node.property.type !== "Identifier" ||
          (node.property.name !== "set" && node.property.name !== "delete")
        ) {
          return;
        }
        const target = unwrap(node.object);
        const aliased =
          target.type === "Identifier" && stores.has(target.name);
        if (aliased || isCookieStore(target)) {
          context.report({ node, messageId: "write" });
        }
      },
    };
  },
};

const argusPlugin = { rules: { "no-unrouted-cookie-write": noUnroutedCookieWrite } };


// Tests, e2e fixtures, and build config drive the real APIs on purpose and
// never ship as Argus code.
const NON_SHIPPING = [
  "__tests__/**",
  "e2e/**",
  "scripts/**",
  "*.config.{ts,mts,cts,mjs,cjs,js,jsx}",
  "*.d.ts",
];

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      "react-hooks/set-state-in-effect": "off",
    },
  },
  // Deny by default. An allowlist of directories missed root entry points
  // (proxy.ts today, instrumentation-client.ts tomorrow) which ship to a
  // browser like anything else, so the scope is every source file with named
  // exemptions rather than four folders.
  {
    files: ["**/*.{ts,tsx,js,jsx,mjs,cjs}"],
    ignores: [...NON_SHIPPING, "lib/browser-storage.ts", "lib/supabase-server.ts"],
    plugins: { argus: argusPlugin },
    rules: {
      "no-restricted-syntax": ["error", ...STORAGE_SELECTORS],
      "argus/no-unrouted-cookie-write": "error",
    },
  },
  // The one sanctioned storage handle. Cookie rules still apply to it.
  {
    files: ["lib/browser-storage.ts"],
    plugins: { argus: argusPlugin },
    rules: { "argus/no-unrouted-cookie-write": "error" },
  },
  // The one sanctioned cookie writer; it asserts before every set. Storage
  // rules still apply to it.
  {
    files: ["lib/supabase-server.ts"],
    rules: {
      "no-restricted-syntax": ["error", ...STORAGE_SELECTORS],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    ".next-*/**",
    "temp-next-build*/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
