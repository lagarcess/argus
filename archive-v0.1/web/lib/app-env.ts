export type AppEnv = "development" | "production";

const DEV_ENV_VALUES = new Set(["dev", "development", "local", "test"]);
const PROD_ENV_VALUES = new Set(["prod", "production"]);

export function normalizeAppEnv(value?: string | null): AppEnv {
  const normalized = (value ?? "").trim().toLowerCase();

  if (PROD_ENV_VALUES.has(normalized)) {
    return "production";
  }
  if (DEV_ENV_VALUES.has(normalized)) {
    return "development";
  }

  // Fall back to Node's runtime mode when NEXT_PUBLIC_APP_ENV is not provided.
  return process.env.NODE_ENV === "production" ? "production" : "development";
}

export const APP_ENV = normalizeAppEnv(process.env.NEXT_PUBLIC_APP_ENV);

export function isDevelopmentEnv(): boolean {
  return APP_ENV === "development";
}

export function isProductionEnv(): boolean {
  return APP_ENV === "production";
}
