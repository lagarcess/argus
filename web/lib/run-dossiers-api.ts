import { apiFetch } from "./argus-api";
import type { PaginatedRunDossiers } from "./run-dossier-contract";

export async function listRunDossiers(
  conversationId: string,
  options: { limit?: number; cursor?: string } = {},
): Promise<PaginatedRunDossiers> {
  const searchParams = new URLSearchParams();
  if (options.limit !== undefined) {
    searchParams.set("limit", String(options.limit));
  }
  if (options.cursor) {
    searchParams.set("cursor", options.cursor);
  }
  const query = searchParams.toString();
  return apiFetch<PaginatedRunDossiers>(
    `/conversations/${encodeURIComponent(conversationId)}/run-dossiers${
      query ? `?${query}` : ""
    }`,
  );
}
