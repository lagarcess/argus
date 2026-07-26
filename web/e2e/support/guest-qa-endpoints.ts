type GuestQaEnvironment = Record<string, string | undefined>;

export type GuestQaEndpointConfig = {
  appOrigin: string;
  appPort: number;
  apiOrigin: string;
  apiPort: number;
  apiBase: string;
  databaseContainer: string;
};

function qaPort(
  env: GuestQaEnvironment,
  name: "ARGUS_GUEST_QA_APP_PORT" | "ARGUS_GUEST_QA_API_PORT",
  fallback: number,
): number {
  const raw = env[name]?.trim();
  if (!raw) return fallback;
  if (!/^\d+$/.test(raw)) {
    throw new Error(`${name} must be an integer loopback port`);
  }
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < 1 || value > 65_535) {
    throw new Error(`${name} must be between 1 and 65535`);
  }
  return value;
}

export function guestQaEndpointConfig(
  env: GuestQaEnvironment = process.env,
): GuestQaEndpointConfig {
  const appPort = qaPort(env, "ARGUS_GUEST_QA_APP_PORT", 3000);
  const apiPort = qaPort(env, "ARGUS_GUEST_QA_API_PORT", 8000);
  if (appPort === apiPort) {
    throw new Error("Guest QA app and API ports must be different");
  }

  const databaseContainer =
    env.ARGUS_GUEST_QA_DB_CONTAINER?.trim() || "supabase_db_argus-qa";
  if (
    !/^supabase_db_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(databaseContainer)
  ) {
    throw new Error("ARGUS_GUEST_QA_DB_CONTAINER is not a safe local container");
  }

  const appOrigin = `http://localhost:${appPort}`;
  const apiOrigin = `http://localhost:${apiPort}`;
  return {
    appOrigin,
    appPort,
    apiOrigin,
    apiPort,
    apiBase: `${apiOrigin}/api/v1`,
    databaseContainer,
  };
}
