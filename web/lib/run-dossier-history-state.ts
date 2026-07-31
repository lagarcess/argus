import type {
  PaginatedRunDossiers,
  RunDossier,
} from "./run-dossier-contract";

export const RUN_DOSSIER_HISTORY_PAGE_LIMIT = 20;

export type RunDossierHistoryState = {
  items: RunDossier[];
  nextCursor: string | null;
  totalRuns: number;
  decidedRuns: number;
  status: "idle" | "loading" | "ready" | "error";
};

export type ListRunDossiers = (
  conversationId: string,
  options: { limit?: number; cursor?: string },
) => Promise<PaginatedRunDossiers>;

type FailedOperation =
  | { kind: "page"; cursor: string | null }
  | { kind: "refresh"; cursors: Array<string | null> };

export type RunDossierHistoryController = {
  getState: () => RunDossierHistoryState;
  subscribe: (listener: () => void) => () => void;
  open: () => Promise<void>;
  loadOlder: () => Promise<void>;
  retry: () => Promise<void>;
  refresh: () => Promise<void>;
  setConversationId: (conversationId: string) => void;
};

function idleState(): RunDossierHistoryState {
  return {
    items: [],
    nextCursor: null,
    totalRuns: 0,
    decidedRuns: 0,
    status: "idle",
  };
}

function requestOptions(cursor: string | null): {
  limit: number;
  cursor?: string;
} {
  return cursor === null
    ? { limit: RUN_DOSSIER_HISTORY_PAGE_LIMIT }
    : { limit: RUN_DOSSIER_HISTORY_PAGE_LIMIT, cursor };
}

function appendUniqueByRunId(
  current: RunDossier[],
  incoming: RunDossier[],
): RunDossier[] {
  const seen = new Set(current.map((item) => item.run_id));
  const items = [...current];
  for (const item of incoming) {
    if (seen.has(item.run_id)) continue;
    seen.add(item.run_id);
    items.push(item);
  }
  return items;
}

export function createRunDossierHistoryController({
  conversationId: initialConversationId,
  listRunDossiers,
}: {
  conversationId: string;
  listRunDossiers: ListRunDossiers;
}): RunDossierHistoryController {
  let conversationId = initialConversationId;
  let state = idleState();
  let requestGeneration = 0;
  let opened = false;
  let loadedPageCursors: Array<string | null> = [];
  let failedOperation: FailedOperation | null = null;
  const listeners = new Set<() => void>();

  const emit = (nextState: RunDossierHistoryState): void => {
    state = nextState;
    for (const listener of listeners) listener();
  };

  const isCurrent = (
    generation: number,
    requestedConversationId: string,
  ): boolean =>
    generation === requestGeneration &&
    requestedConversationId === conversationId;

  const readPage = async (
    cursor: string | null,
    mode: "replace" | "append",
  ): Promise<void> => {
    const generation = ++requestGeneration;
    const requestedConversationId = conversationId;
    const preservedState = state;
    failedOperation = null;
    emit({ ...state, status: "loading" });

    try {
      const response = await listRunDossiers(
        requestedConversationId,
        requestOptions(cursor),
      );
      if (!isCurrent(generation, requestedConversationId)) return;

      const items =
        mode === "append"
          ? appendUniqueByRunId(preservedState.items, response.items)
          : appendUniqueByRunId([], response.items);
      if (mode === "replace") {
        loadedPageCursors = [cursor];
      } else if (!loadedPageCursors.includes(cursor)) {
        loadedPageCursors = [...loadedPageCursors, cursor];
      }
      emit({
        items,
        nextCursor: response.next_cursor,
        totalRuns: response.total_runs,
        decidedRuns: response.decided_runs,
        status: "ready",
      });
    } catch {
      if (!isCurrent(generation, requestedConversationId)) return;
      failedOperation = { kind: "page", cursor };
      emit({ ...preservedState, status: "error" });
    }
  };

  const refreshCursors = async (
    cursors: Array<string | null>,
  ): Promise<void> => {
    const generation = ++requestGeneration;
    const requestedConversationId = conversationId;
    const preservedState = state;
    failedOperation = null;
    emit({ ...state, status: "loading" });

    try {
      let items: RunDossier[] = [];
      let latestResponse: PaginatedRunDossiers | null = null;
      for (const cursor of cursors) {
        const response = await listRunDossiers(
          requestedConversationId,
          requestOptions(cursor),
        );
        if (!isCurrent(generation, requestedConversationId)) return;
        items = appendUniqueByRunId(items, response.items);
        latestResponse = response;
      }
      if (!latestResponse || !isCurrent(generation, requestedConversationId)) {
        return;
      }

      loadedPageCursors = [...cursors];
      emit({
        items,
        nextCursor: latestResponse.next_cursor,
        totalRuns: latestResponse.total_runs,
        decidedRuns: latestResponse.decided_runs,
        status: "ready",
      });
    } catch {
      if (!isCurrent(generation, requestedConversationId)) return;
      failedOperation = { kind: "refresh", cursors: [...cursors] };
      emit({ ...preservedState, status: "error" });
    }
  };

  return {
    getState: () => state,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    open: async () => {
      if (opened) return;
      opened = true;
      await readPage(null, "replace");
    },
    loadOlder: async () => {
      if (!opened || state.status === "loading" || !state.nextCursor) return;
      await readPage(state.nextCursor, "append");
    },
    retry: async () => {
      const operation = failedOperation;
      if (!operation || state.status === "loading") return;
      if (operation.kind === "refresh") {
        await refreshCursors(operation.cursors);
        return;
      }
      await readPage(
        operation.cursor,
        operation.cursor === null ? "replace" : "append",
      );
    },
    refresh: async () => {
      if (!opened) return;
      const cursors =
        loadedPageCursors.length > 0 ? [...loadedPageCursors] : [null];
      await refreshCursors(cursors);
    },
    setConversationId: (nextConversationId) => {
      if (nextConversationId === conversationId) return;
      requestGeneration += 1;
      conversationId = nextConversationId;
      opened = false;
      loadedPageCursors = [];
      failedOperation = null;
      emit(idleState());
    },
  };
}
