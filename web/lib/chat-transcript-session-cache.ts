/**
 * Browser-session transcript cache policy for issue #252.
 *
 * - Memory only: never write transcripts to localStorage, IndexedDB, or a
 *   service worker.
 * - Keys include authenticated user id plus conversation id.
 * - Entries are fresh for 30 seconds and LRU-bounded to 8 entries / 2 MiB of
 *   estimated serialized transcript payload.
 * - A new-key miss emits `snapshot: null`; it never reuses another
 *   conversation's visible content. A stale same-key refresh keeps the last
 *   successful snapshot visible.
 * - Message send, retry, recovery, durable job completion, and delete evict
 *   only the owning transcript and scroll state. Rename preserves the entry
 *   because conversation titles are not part of the transcript snapshot.
 * - Logout or authenticated-user change aborts pending loads and clears every
 *   transcript and scroll entry.
 * - Abort reduces wasted work, while the monotonic navigation generation is
 *   the correctness guard when a loader ignores AbortSignal.
 *
 * ChatInterface integration is intentionally separate so the cache layer can
 * be reverted without removing latest-navigation protection.
 */

export const TRANSCRIPT_CACHE_POLICY = {
  freshForMs: 30_000,
  maxEntries: 8,
  maxEstimatedBytes: 2 * 1024 * 1024,
} as const;

export type TranscriptCacheIdentity = Readonly<{
  userId: string;
  conversationId: string;
}>;

export type TranscriptMutation =
  | "message_send"
  | "retry"
  | "recovery"
  | "durable_job_completion"
  | "conversation_rename"
  | "conversation_delete";

export type TranscriptInvalidationResult = "evicted" | "preserved" | "unchanged";

export type CachedTranscript<TSnapshot> = Readonly<{
  snapshot: TSnapshot;
  freshness: "fresh" | "stale";
  loadedAt: number;
}>;

export type TranscriptNavigationState<TSnapshot> =
  | Readonly<{
      phase: "loading";
      source: "cache_miss";
      snapshot: null;
    }>
  | Readonly<{
      phase: "refreshing";
      source: "stale_cache";
      snapshot: TSnapshot;
    }>
  | Readonly<{
      phase: "ready";
      source: "fresh_cache" | "network";
      snapshot: TSnapshot;
    }>
  | Readonly<{
      phase: "error";
      source: "network";
      snapshot: TSnapshot | null;
      error: unknown;
    }>;

export type TranscriptNavigationInput<TSnapshot> = TranscriptCacheIdentity &
  Readonly<{
    load: (signal: AbortSignal) => Promise<TSnapshot>;
    onState: (state: TranscriptNavigationState<TSnapshot>) => void;
  }>;

export type TranscriptNavigationHandle = Readonly<{
  cacheStatus: "fresh" | "stale" | "miss";
  completion: Promise<void>;
}>;

type TranscriptSessionCacheOptions<TSnapshot> = Readonly<{
  freshForMs?: number;
  maxEntries?: number;
  maxEstimatedBytes?: number;
  estimateBytes?: (snapshot: TSnapshot) => number;
  now?: () => number;
}>;

type CacheEntry<TSnapshot> = {
  snapshot?: TSnapshot;
  loadedAt?: number;
  scrollTop?: number;
  estimatedBytes: number;
};

type InFlightLoad<TSnapshot> = {
  controller: AbortController;
  promise: Promise<TSnapshot>;
};

type ActiveNavigation = Readonly<{
  key: string;
  generation: number;
}>;

function normalizedId(value: string, name: "userId" | "conversationId"): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(`${name} must be a non-empty string.`);
  }
  return normalized;
}

function estimatedSerializedBytes(value: unknown): number {
  try {
    return JSON.stringify(value).length * 2;
  } catch {
    return Number.POSITIVE_INFINITY;
  }
}

function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    (error as { name?: unknown }).name === "AbortError"
  );
}

export class TranscriptSessionCache<TSnapshot> {
  private readonly freshForMs: number;
  private readonly maxEntries: number;
  private readonly maxEstimatedBytes: number;
  private readonly estimateBytes: (snapshot: TSnapshot) => number;
  private readonly now: () => number;
  private readonly entries = new Map<string, CacheEntry<TSnapshot>>();
  private readonly inFlightLoads = new Map<string, InFlightLoad<TSnapshot>>();
  private readonly keyRevisions = new Map<string, number>();
  private authenticatedUserId: string | null = null;
  private activeNavigation: ActiveNavigation | null = null;
  private navigationGeneration = 0;
  private sessionEpoch = 0;
  private totalEstimatedBytes = 0;

  constructor(options: TranscriptSessionCacheOptions<TSnapshot> = {}) {
    this.freshForMs = options.freshForMs ?? TRANSCRIPT_CACHE_POLICY.freshForMs;
    this.maxEntries = options.maxEntries ?? TRANSCRIPT_CACHE_POLICY.maxEntries;
    this.maxEstimatedBytes =
      options.maxEstimatedBytes ?? TRANSCRIPT_CACHE_POLICY.maxEstimatedBytes;
    this.estimateBytes = options.estimateBytes ?? estimatedSerializedBytes;
    this.now = options.now ?? Date.now;
  }

  navigate(input: TranscriptNavigationInput<TSnapshot>): TranscriptNavigationHandle {
    const identity = this.resolveIdentity(input);
    const key = this.cacheKey(identity);
    const previousNavigation = this.activeNavigation;
    const generation = ++this.navigationGeneration;

    if (previousNavigation && previousNavigation.key !== key) {
      this.abortLoad(previousNavigation.key);
    }
    this.activeNavigation = { key, generation };

    const cached = this.readSnapshotByKey(key);
    if (cached?.freshness === "fresh") {
      input.onState({
        phase: "ready",
        source: "fresh_cache",
        snapshot: cached.snapshot,
      });
      return { cacheStatus: "fresh", completion: Promise.resolve() };
    }

    const previousSnapshot = cached?.snapshot ?? null;
    if (cached) {
      input.onState({
        phase: "refreshing",
        source: "stale_cache",
        snapshot: cached.snapshot,
      });
    } else {
      input.onState({ phase: "loading", source: "cache_miss", snapshot: null });
    }

    const inFlight = this.loadOnce(key, input.load);
    const completion = inFlight.promise
      .then((snapshot) => {
        if (!this.isLatestNavigation(key, generation)) {
          return;
        }
        input.onState({ phase: "ready", source: "network", snapshot });
      })
      .catch((error: unknown) => {
        if (!this.isLatestNavigation(key, generation)) {
          return;
        }
        if (isAbortError(error) && inFlight.controller.signal.aborted) {
          return;
        }
        input.onState({
          phase: "error",
          source: "network",
          snapshot: previousSnapshot,
          error,
        });
      });

    return {
      cacheStatus: cached ? "stale" : "miss",
      completion,
    };
  }

  readSnapshot(identity: TranscriptCacheIdentity): CachedTranscript<TSnapshot> | null {
    const resolved = this.resolveIdentity(identity);
    return this.readSnapshotByKey(this.cacheKey(resolved));
  }

  rememberScroll(
    input: TranscriptCacheIdentity & Readonly<{ scrollTop: number }>,
  ): void {
    const identity = this.resolveIdentity(input);
    const key = this.cacheKey(identity);
    const existing = this.entries.get(key);
    const scrollTop = Number.isFinite(input.scrollTop)
      ? Math.max(0, input.scrollTop)
      : 0;
    this.writeEntry(key, {
      ...existing,
      scrollTop,
      estimatedBytes: this.entryBytes(existing?.snapshot, scrollTop),
    });
  }

  readScroll(identity: TranscriptCacheIdentity): number | null {
    const resolved = this.resolveIdentity(identity);
    const key = this.cacheKey(resolved);
    const entry = this.entries.get(key);
    if (entry?.scrollTop === undefined) {
      return null;
    }
    this.touchEntry(key, entry);
    return entry.scrollTop;
  }

  invalidateForMutation(
    input: TranscriptCacheIdentity & Readonly<{ mutation: TranscriptMutation }>,
  ): TranscriptInvalidationResult {
    const identity = this.resolveIdentity(input);
    if (input.mutation === "conversation_rename") {
      return "preserved";
    }

    const key = this.cacheKey(identity);
    const hadEntry = this.entries.has(key);
    const hadLoad = this.inFlightLoads.has(key);
    this.keyRevisions.set(key, this.keyRevision(key) + 1);
    this.abortLoad(key);
    this.deleteEntry(key);
    if (this.activeNavigation?.key === key) {
      this.activeNavigation = null;
      this.navigationGeneration += 1;
    }
    return hadEntry || hadLoad ? "evicted" : "unchanged";
  }

  clearAuthenticatedState(): void {
    for (const load of this.inFlightLoads.values()) {
      load.controller.abort();
    }
    this.inFlightLoads.clear();
    this.entries.clear();
    this.keyRevisions.clear();
    this.totalEstimatedBytes = 0;
    this.authenticatedUserId = null;
    this.activeNavigation = null;
    this.navigationGeneration += 1;
    this.sessionEpoch += 1;
  }

  private resolveIdentity(identity: TranscriptCacheIdentity): TranscriptCacheIdentity {
    const resolved = {
      userId: normalizedId(identity.userId, "userId"),
      conversationId: normalizedId(identity.conversationId, "conversationId"),
    };
    if (
      this.authenticatedUserId !== null &&
      this.authenticatedUserId !== resolved.userId
    ) {
      this.clearAuthenticatedState();
    }
    this.authenticatedUserId = resolved.userId;
    return resolved;
  }

  private cacheKey(identity: TranscriptCacheIdentity): string {
    return JSON.stringify([identity.userId, identity.conversationId]);
  }

  private readSnapshotByKey(key: string): CachedTranscript<TSnapshot> | null {
    const entry = this.entries.get(key);
    if (entry?.snapshot === undefined || entry.loadedAt === undefined) {
      return null;
    }
    this.touchEntry(key, entry);
    const age = Math.max(0, this.now() - entry.loadedAt);
    return {
      snapshot: entry.snapshot,
      freshness: age < this.freshForMs ? "fresh" : "stale",
      loadedAt: entry.loadedAt,
    };
  }

  private loadOnce(
    key: string,
    load: (signal: AbortSignal) => Promise<TSnapshot>,
  ): InFlightLoad<TSnapshot> {
    const existing = this.inFlightLoads.get(key);
    if (existing) {
      return existing;
    }

    const controller = new AbortController();
    const epoch = this.sessionEpoch;
    const revision = this.keyRevision(key);
    let loadPromise: Promise<TSnapshot>;
    try {
      loadPromise = load(controller.signal);
    } catch (error) {
      loadPromise = Promise.reject(error);
    }
    const promise = loadPromise.then((snapshot) => {
      if (
        !controller.signal.aborted &&
        this.sessionEpoch === epoch &&
        this.keyRevision(key) === revision
      ) {
        this.rememberSnapshot(key, snapshot);
      }
      return snapshot;
    });

    const inFlight = { controller, promise };
    this.inFlightLoads.set(key, inFlight);
    void promise.then(
      () => this.finishLoad(key, inFlight),
      () => this.finishLoad(key, inFlight),
    );
    return inFlight;
  }

  private finishLoad(key: string, load: InFlightLoad<TSnapshot>): void {
    if (this.inFlightLoads.get(key) === load) {
      this.inFlightLoads.delete(key);
    }
  }

  private abortLoad(key: string): void {
    const load = this.inFlightLoads.get(key);
    if (!load) {
      return;
    }
    this.inFlightLoads.delete(key);
    load.controller.abort();
  }

  private rememberSnapshot(key: string, snapshot: TSnapshot): void {
    const existing = this.entries.get(key);
    this.writeEntry(key, {
      ...existing,
      snapshot,
      loadedAt: this.now(),
      estimatedBytes: this.entryBytes(snapshot, existing?.scrollTop),
    });
  }

  private entryBytes(snapshot: TSnapshot | undefined, scrollTop?: number): number {
    const rawSnapshotBytes = snapshot === undefined ? 0 : this.estimateBytes(snapshot);
    const snapshotBytes = Number.isFinite(rawSnapshotBytes)
      ? Math.max(0, rawSnapshotBytes)
      : this.maxEstimatedBytes + 1;
    return snapshotBytes + (scrollTop === undefined ? 0 : 8);
  }

  private writeEntry(key: string, entry: CacheEntry<TSnapshot>): void {
    this.deleteEntry(key);
    this.entries.set(key, entry);
    this.totalEstimatedBytes += entry.estimatedBytes;
    this.enforceBounds();
  }

  private touchEntry(key: string, entry: CacheEntry<TSnapshot>): void {
    this.entries.delete(key);
    this.entries.set(key, entry);
  }

  private deleteEntry(key: string): void {
    const previous = this.entries.get(key);
    if (!previous) {
      return;
    }
    this.totalEstimatedBytes = Math.max(
      0,
      this.totalEstimatedBytes - previous.estimatedBytes,
    );
    this.entries.delete(key);
  }

  private enforceBounds(): void {
    while (
      this.entries.size > this.maxEntries ||
      this.totalEstimatedBytes > this.maxEstimatedBytes
    ) {
      const oldestKey = this.entries.keys().next().value as string | undefined;
      if (!oldestKey) {
        break;
      }
      this.deleteEntry(oldestKey);
    }
  }

  private keyRevision(key: string): number {
    return this.keyRevisions.get(key) ?? 0;
  }

  private isLatestNavigation(key: string, generation: number): boolean {
    return (
      this.activeNavigation?.key === key &&
      this.activeNavigation.generation === generation
    );
  }
}
