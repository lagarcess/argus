import { getMemoryAvailability } from "./memory-api";

// Temporary chat: conversations the user opted out of memory. Client-held
// state; opting out only ever disables recall and proposals for that
// conversation, so a lost entry fails safe.
const MEMORY_OPT_OUT_STORAGE_KEY = "argus.memoryOptOutConversations.v1";

// Session truth: the toggle the user sees must be the toggle the transport
// sends, even when persistence is blocked. localStorage only carries the
// choice across reloads, best effort.
const sessionOptOut = new Map<string, boolean>();

function readOptOutIds(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(MEMORY_OPT_OUT_STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((item): item is string => typeof item === "string"));
  } catch {
    return new Set();
  }
}

function writeOptOutIds(ids: Set<string>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      MEMORY_OPT_OUT_STORAGE_KEY,
      JSON.stringify([...ids].sort()),
    );
  } catch {
    // Storage may be unavailable; the mode simply does not persist.
  }
}

export function isConversationMemoryOptOut(conversationId: string): boolean {
  const held = sessionOptOut.get(conversationId);
  if (held !== undefined) return held;
  return readOptOutIds().has(conversationId);
}

export function setConversationMemoryOptOut(
  conversationId: string,
  optOut: boolean,
): void {
  sessionOptOut.set(conversationId, optOut);
  const ids = readOptOutIds();
  if (optOut) {
    ids.add(conversationId);
  } else {
    ids.delete(conversationId);
  }
  writeOptOutIds(ids);
}

// Availability is stable for a session; cache the probe so menus, result
// cards, and chat share one request. A probe failure reads as unavailable.
let availabilityPromise: Promise<boolean> | null = null;

export function memoryAvailable(): Promise<boolean> {
  if (availabilityPromise === null) {
    availabilityPromise = getMemoryAvailability()
      .then((response) => response.available === true)
      .catch(() => {
        availabilityPromise = null;
        return false;
      });
  }
  return availabilityPromise;
}

export function resetMemoryAvailabilityCache(): void {
  availabilityPromise = null;
}
