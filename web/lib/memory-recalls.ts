// Typed reader for the backend's post-turn memory recall annotation. The
// backend only ever attaches it after interpretation and simulation finish;
// the client renders it as context and never feeds it back into a request.

export type MemoryRecallItem = {
  record_id: string;
  label: string;
  value: string;
  category: string;
};

export function memoryRecallsFromValue(
  value: unknown,
): MemoryRecallItem[] | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const items: MemoryRecallItem[] = [];
  for (const entry of value) {
    if (typeof entry !== "object" || entry === null) return null;
    const record = entry as Record<string, unknown>;
    const recordId = record.record_id;
    const label = record.label;
    const content = record.value;
    const category = record.category;
    if (
      typeof recordId !== "string" ||
      typeof label !== "string" ||
      typeof content !== "string" ||
      typeof category !== "string"
    ) {
      return null;
    }
    items.push({
      record_id: recordId,
      label,
      value: content,
      category,
    });
  }
  return items;
}

export function memoryRecallsFromMetadata(
  metadata: Record<string, unknown>,
): MemoryRecallItem[] | null {
  return memoryRecallsFromValue(metadata.memory_recalls);
}
