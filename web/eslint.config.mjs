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

// Cookie WRITES only. Reading cookies is ordinary work and stays free; it is
// setting one that adds browser state the disclosure has to cover.
const COOKIE_SELECTORS = [
  {
    selector:
      "MemberExpression[property.name='set'][object.property.name='cookies']",
    message:
      "Route cookie writes through lib/supabase-server.ts, which asserts against COOKIE_DISCLOSURE_RULES first.",
  },
  {
    selector:
      "CallExpression[callee.callee.name='cookies'][callee.property.name='set']",
    message:
      "Route cookie writes through lib/supabase-server.ts, which asserts against COOKIE_DISCLOSURE_RULES first.",
  },
];


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
    rules: {
      "no-restricted-syntax": ["error", ...STORAGE_SELECTORS, ...COOKIE_SELECTORS],
    },
  },
  // The one sanctioned storage handle. Cookie rules still apply to it.
  {
    files: ["lib/browser-storage.ts"],
    rules: {
      "no-restricted-syntax": ["error", ...COOKIE_SELECTORS],
    },
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
