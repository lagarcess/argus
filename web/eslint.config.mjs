import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      "react-hooks/set-state-in-effect": "off",
    },
  },
  // Browser state must go through lib/browser-storage.ts, whose registry the
  // privacy disclosure is derived from. Reaching the APIs directly, including
  // by aliasing or destructuring a handle, is what these selectors catch, so
  // adding an undisclosed key means disabling a rule in view of a reviewer
  // rather than writing ordinary-looking code.
  // Product source only. Tests and e2e fixtures drive the real APIs on
  // purpose, including the observation spec that instruments them, and they
  // never ship to a browser as Argus code.
  {
    files: [
      "app/**/*.{ts,tsx}",
      "components/**/*.{ts,tsx}",
      "hooks/**/*.{ts,tsx}",
      "lib/**/*.{ts,tsx}",
    ],
    ignores: ["lib/browser-storage.ts"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "MemberExpression[property.name=/^(localStorage|sessionStorage)$/]",
          message:
            "Use lib/browser-storage.ts. Its registry is what the privacy policy discloses.",
        },
        {
          selector: "Identifier[name=/^(localStorage|sessionStorage)$/]",
          message:
            "Use lib/browser-storage.ts. Its registry is what the privacy policy discloses.",
        },
        {
          selector:
            "MemberExpression[object.name='document'][property.name='cookie']",
          message:
            "Argus does not write cookies from the browser. Cookies are set by the backend through argus.api.browser_cookies.",
        },
      ],
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
