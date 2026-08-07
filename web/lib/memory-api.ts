import { apiFetch } from "./argus-api-transport";

export type MemoryCategory =
  | "personalization_preference"
  | "workflow_preference"
  | "explicit_decision_note"
  | "past_session_anchor";

export const ALL_MEMORY_CATEGORIES: MemoryCategory[] = [
  "personalization_preference",
  "workflow_preference",
  "explicit_decision_note",
  "past_session_anchor",
];

export type MemoryProvenanceRef = {
  source_kind: string;
  source_id: string;
  source_version: string;
};

export type MemoryConsentReceipt = {
  id: string;
  action: "direct_enable" | "candidate_confirmation";
  candidate_id: string | null;
  requested_scope: MemoryCategory[];
  granted_scope: MemoryCategory[];
  effective_scope: MemoryCategory[];
  recorded_at: string;
};

export type MemoryRecord = {
  id: string;
  candidate_id: string;
  category: MemoryCategory;
  label: string;
  value: string;
  provenance: MemoryProvenanceRef[];
  consent_receipt: MemoryConsentReceipt;
  revision: number;
  created_at: string;
  updated_at: string;
};

export type MemoryCandidate = {
  id: string;
  category: MemoryCategory;
  label: string;
  value: string;
  future_benefit: string;
  provenance: MemoryProvenanceRef[];
  trigger: string;
  sensitivity: { status: string; flags: string[] };
  opt_in_scope: MemoryCategory[];
  created_at: string;
};

export type MemorySettings = {
  enabled: boolean;
  enabled_categories: MemoryCategory[];
};

export type MemoryExplanation = {
  record_id: string;
  category: MemoryCategory;
  provenance: MemoryProvenanceRef[];
  consent_receipt_id: string;
  consent_schema_version: string;
  confirmed_at: string;
};

export type MemoryControlResult = {
  changed: boolean;
  record: MemoryRecord | null;
  provider_status: string;
};

export type MemoryExportDocument = {
  format: string;
  exported_at: string;
  settings: MemorySettings;
  records: MemoryRecord[];
};

export async function getMemoryAvailability(): Promise<{ available: boolean }> {
  return apiFetch<{ available: boolean }>("/memory/availability");
}

export async function getMemorySettings(): Promise<MemorySettings> {
  return apiFetch<MemorySettings>("/memory/settings");
}

export async function listMemoryRecords(): Promise<{ records: MemoryRecord[] }> {
  return apiFetch<{ records: MemoryRecord[] }>("/memory/records");
}

export async function explainMemoryRecord(
  recordId: string,
): Promise<MemoryExplanation> {
  return apiFetch<MemoryExplanation>(
    `/memory/records/${encodeURIComponent(recordId)}/explanation`,
  );
}

export async function editMemoryRecord(
  recordId: string,
  changes: { value?: string; label?: string },
): Promise<MemoryControlResult> {
  return apiFetch<MemoryControlResult>(
    `/memory/records/${encodeURIComponent(recordId)}`,
    { method: "PATCH", body: JSON.stringify(changes) },
  );
}

export async function deleteMemoryRecord(
  recordId: string,
): Promise<MemoryControlResult> {
  return apiFetch<MemoryControlResult>(
    `/memory/records/${encodeURIComponent(recordId)}`,
    { method: "DELETE" },
  );
}

export async function enableMemory(
  categories: MemoryCategory[],
): Promise<MemorySettings> {
  return apiFetch<MemorySettings>("/memory/enable", {
    method: "POST",
    body: JSON.stringify({ categories }),
  });
}

export async function disableMemory(): Promise<MemoryControlResult> {
  return apiFetch<MemoryControlResult>("/memory/disable", { method: "POST" });
}

export async function resetMemory(): Promise<MemoryControlResult> {
  return apiFetch<MemoryControlResult>("/memory/reset", { method: "POST" });
}

export async function exportMemory(): Promise<MemoryExportDocument> {
  return apiFetch<MemoryExportDocument>("/memory/export");
}

export async function proposeSavedDecisionMemory(payload: {
  label: string;
  value: string;
  provenance: MemoryProvenanceRef;
}): Promise<{ created: boolean; candidate: MemoryCandidate | null }> {
  return apiFetch<{ created: boolean; candidate: MemoryCandidate | null }>(
    "/memory/candidates/saved-decision",
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function confirmMemoryCandidate(candidateId: string): Promise<{
  created: boolean;
  record: MemoryRecord | null;
  consent_receipt: MemoryConsentReceipt | null;
}> {
  return apiFetch(
    `/memory/candidates/${encodeURIComponent(candidateId)}/confirm`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

export async function declineMemoryCandidate(
  candidateId: string,
): Promise<{ declined: boolean }> {
  return apiFetch<{ declined: boolean }>(
    `/memory/candidates/${encodeURIComponent(candidateId)}/decline`,
    { method: "POST" },
  );
}
