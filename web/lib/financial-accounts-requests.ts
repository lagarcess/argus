import type { CreateFinancialAccountRequest } from "./financial-accounts-api";

export interface FinancialAccountRequestOwner {
  setIdentity(userId: string | null): void;
  execute<T>(operation: (signal: AbortSignal) => Promise<T>): Promise<T>;
  dispose(): void;
}

function retiredRequest(): DOMException {
  return new DOMException("Financial account request retired", "AbortError");
}

/** One lifetime per verified identity, including a fresh lifetime after A -> B -> A. */
export function createFinancialAccountRequestOwner(
  initialUserId: string | null = null,
): FinancialAccountRequestOwner {
  let identity = initialUserId;
  let disposed = false;
  const active = new Set<AbortController>();

  function invalidate(): void {
    for (const controller of active) controller.abort(retiredRequest());
    active.clear();
  }

  return {
    setIdentity(userId) {
      if (disposed || identity === userId) return;
      identity = userId;
      invalidate();
    },
    async execute<T>(operation: (signal: AbortSignal) => Promise<T>): Promise<T> {
      if (disposed || identity === null) throw retiredRequest();
      const controller = new AbortController();
      active.add(controller);
      let rejectAbort!: (reason: unknown) => void;
      const aborted = new Promise<never>((_resolve, reject) => { rejectAbort = reject; });
      const onAbort = (): void => rejectAbort(controller.signal.reason);
      controller.signal.addEventListener("abort", onAbort, { once: true });
      const pending = Promise.resolve().then(() => {
        controller.signal.throwIfAborted();
        return operation(controller.signal);
      });
      try {
        const result = await Promise.race([pending, aborted]);
        controller.signal.throwIfAborted();
        return result;
      } catch (error) {
        controller.signal.throwIfAborted();
        throw error;
      } finally {
        controller.signal.removeEventListener("abort", onAbort);
        active.delete(controller);
      }
    },
    dispose() {
      disposed = true;
      identity = null;
      invalidate();
    },
  };
}

export interface FinancialAccountCreateAttempt {
  readonly payload: Readonly<CreateFinancialAccountRequest>;
  readonly idempotencyKey: string;
}

/** The create schema is flat: copying and freezing detaches every editable field. */
export function createFinancialAccountAttempt(
  payload: CreateFinancialAccountRequest,
  idempotencyKey: string = crypto.randomUUID(),
): FinancialAccountCreateAttempt {
  return Object.freeze({ payload: Object.freeze({ ...payload }), idempotencyKey });
}
