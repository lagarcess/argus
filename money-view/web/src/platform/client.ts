import { z } from "zod";

export class APIError extends Error {
  constructor(
    public code: string,
    public status = 0,
  ) {
    super(code);
    this.name = "APIError";
  }
}

export async function requestResponse(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  let response: Response;
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type"))
    headers.set("Content-Type", "application/json");
  try {
    response = await fetch(
      path.startsWith("/api/") ? path : `/api/platform${path}`,
      {
        ...options,
        credentials: "same-origin",
        headers,
      },
    );
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new APIError("network_error");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const code = body?.code ?? body?.detail?.code ?? `http_${response.status}`;
    if (response.status === 401 && code === "authentication_required")
      window.dispatchEvent(new Event("clara:session-expired"));
    throw new APIError(code, response.status);
  }
  return response;
}

export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit = {},
): Promise<T> {
  const response = await requestResponse(path, options);
  const parsed = schema.safeParse(await response.json().catch(() => null));
  if (!parsed.success) throw new APIError("invalid_response", response.status);
  return parsed.data;
}
