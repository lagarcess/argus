"use client";

import { useEffect, useLayoutEffect, useState, type RefObject } from "react";

import type { UseConversationActivityResult } from "./useConversationActivity";

export type ConversationActivityViewportInputs = Readonly<{
  activeRouteConversationId: string | null;
  activeConversationId: string | null;
  activeConversationIdRef: string | null;
  readyTranscriptConversationId: string | null;
  transcriptRoot: HTMLElement | null;
  sentinel: HTMLElement | null;
  hydrationComplete: boolean;
  attentionCursor: string | null;
  manualUnreadGuard: boolean;
  markReadPending: boolean;
}>;

type ObserveLatestActivityOptions = Readonly<{
  root: HTMLElement;
  sentinel: HTMLElement;
  onIntersectionChange: (intersecting: boolean) => void;
}>;

export type ConversationActivityViewportEffectsAdapter = Readonly<{
  observeLatestActivity: (options: ObserveLatestActivityOptions) => () => void;
  subscribeWindowFocus: (callback: () => void) => () => void;
  subscribeWindowBlur: (callback: () => void) => () => void;
  subscribeVisibilityChange: (callback: () => void) => () => void;
  isDocumentVisible: () => boolean;
  isWindowFocused: () => boolean;
}>;

export type ConversationActivityViewportRuntime = Readonly<{
  start: () => void;
  dispose: () => void;
  updateInputs: (inputs: ConversationActivityViewportInputs) => void;
}>;

type CreateConversationActivityViewportRuntimeOptions = Readonly<{
  inputs: ConversationActivityViewportInputs;
  effects: ConversationActivityViewportEffectsAdapter;
  markRead: (conversationId: string, throughCursor: string) => Promise<void>;
  resetViewEpoch: (conversationId: string) => void;
}>;

const createBrowserEffectsAdapter =
  (): ConversationActivityViewportEffectsAdapter => ({
    observeLatestActivity: ({ root, sentinel, onIntersectionChange }) => {
      if (typeof IntersectionObserver === "undefined") return () => undefined;
      const observer = new IntersectionObserver(
        (entries) => {
          const entry = entries.find((candidate) => candidate.target === sentinel);
          if (entry) onIntersectionChange(entry.isIntersecting);
        },
        { root, threshold: 1 },
      );
      observer.observe(sentinel);
      return () => observer.disconnect();
    },
    subscribeWindowFocus: (callback) => {
      if (typeof window === "undefined") return () => undefined;
      window.addEventListener("focus", callback);
      return () => window.removeEventListener("focus", callback);
    },
    subscribeWindowBlur: (callback) => {
      if (typeof window === "undefined") return () => undefined;
      window.addEventListener("blur", callback);
      return () => window.removeEventListener("blur", callback);
    },
    subscribeVisibilityChange: (callback) => {
      if (typeof document === "undefined") return () => undefined;
      document.addEventListener("visibilitychange", callback);
      return () => document.removeEventListener("visibilitychange", callback);
    },
    isDocumentVisible: () =>
      typeof document === "undefined" || document.visibilityState === "visible",
    isWindowFocused: () =>
      typeof document === "undefined" || document.hasFocus(),
  });

const readKey = (conversationId: string, cursor: string): string =>
  JSON.stringify([conversationId, cursor]);

const proofFingerprint = (inputs: ConversationActivityViewportInputs): string =>
  JSON.stringify([
    inputs.activeRouteConversationId,
    inputs.activeConversationId,
    inputs.activeConversationIdRef,
    inputs.readyTranscriptConversationId,
    inputs.transcriptRoot?.dataset.conversationId ?? null,
    inputs.hydrationComplete,
    inputs.attentionCursor,
    inputs.manualUnreadGuard,
  ]);

class ConversationActivityViewportOwner
  implements ConversationActivityViewportRuntime
{
  private inputs: ConversationActivityViewportInputs;
  private started = false;
  private disposed = false;
  private sentinelIntersecting = false;
  private meaningfulTrigger = 0;
  private observerEpoch = 0;
  private environmentFingerprint = "";
  private cancelObserver: (() => void) | null = null;
  private unsubscribeFocus: (() => void) | null = null;
  private unsubscribeBlur: (() => void) | null = null;
  private unsubscribeVisibility: (() => void) | null = null;
  private readonly acknowledgedReads = new Set<string>();
  private readonly inFlightReads = new Set<string>();
  private readonly resolvedReads = new Map<
    string,
    Readonly<{ conversationId: string; cursor: string }>
  >();
  private readonly failedReadTrigger = new Map<string, number>();

  constructor(
    private readonly options: CreateConversationActivityViewportRuntimeOptions,
  ) {
    this.inputs = options.inputs;
  }

  start = (): void => {
    if (this.started || this.disposed) return;
    this.started = true;
    this.environmentFingerprint = this.currentEnvironmentFingerprint();
    this.unsubscribeFocus = this.options.effects.subscribeWindowFocus(
      this.handleEnvironmentChange,
    );
    this.unsubscribeBlur = this.options.effects.subscribeWindowBlur(
      this.handleEnvironmentChange,
    );
    this.unsubscribeVisibility =
      this.options.effects.subscribeVisibilityChange(
        this.handleEnvironmentChange,
      );
    this.attachObserver();
  };

  dispose = (): void => {
    if (this.disposed) return;
    this.disposed = true;
    this.started = false;
    this.observerEpoch += 1;
    this.cancelObserver?.();
    this.cancelObserver = null;
    this.unsubscribeFocus?.();
    this.unsubscribeBlur?.();
    this.unsubscribeVisibility?.();
    this.unsubscribeFocus = null;
    this.unsubscribeBlur = null;
    this.unsubscribeVisibility = null;
  };

  updateInputs = (inputs: ConversationActivityViewportInputs): void => {
    if (this.disposed) return;
    const previous = this.inputs;
    if (
      previous.activeConversationId &&
      previous.activeConversationId !== inputs.activeConversationId
    ) {
      this.options.resetViewEpoch(previous.activeConversationId);
    }
    const observerChanged =
      previous.transcriptRoot !== inputs.transcriptRoot ||
      previous.sentinel !== inputs.sentinel;
    const proofChanged = proofFingerprint(previous) !== proofFingerprint(inputs);
    this.inputs = inputs;
    if (proofChanged) this.meaningfulTrigger += 1;
    this.settleResolvedReads();
    if (observerChanged && this.started) this.attachObserver();
    this.evaluateReadProof();
  };

  private attachObserver(): void {
    this.observerEpoch += 1;
    const epoch = this.observerEpoch;
    this.cancelObserver?.();
    this.cancelObserver = null;
    this.sentinelIntersecting = false;
    const { transcriptRoot, sentinel } = this.inputs;
    if (!this.started || !transcriptRoot || !sentinel) return;
    this.cancelObserver = this.options.effects.observeLatestActivity({
      root: transcriptRoot,
      sentinel,
      onIntersectionChange: (intersecting) => {
        if (
          this.disposed ||
          !this.started ||
          epoch !== this.observerEpoch
        ) {
          return;
        }
        if (intersecting !== this.sentinelIntersecting) {
          this.sentinelIntersecting = intersecting;
          this.meaningfulTrigger += 1;
        }
        if (intersecting) this.evaluateReadProof();
      },
    });
  }

  private handleEnvironmentChange = (): void => {
    if (this.disposed || !this.started) return;
    const nextFingerprint = this.currentEnvironmentFingerprint();
    if (nextFingerprint === this.environmentFingerprint) return;
    this.environmentFingerprint = nextFingerprint;
    this.meaningfulTrigger += 1;
    this.evaluateReadProof();
  };

  private currentEnvironmentFingerprint(): string {
    return JSON.stringify([
      this.options.effects.isDocumentVisible(),
      this.options.effects.isWindowFocused(),
    ]);
  }

  private proofConversation(): Readonly<{
    conversationId: string;
    cursor: string;
  }> | null {
    const conversationId = this.inputs.activeConversationId;
    const cursor = this.inputs.attentionCursor;
    if (
      !conversationId ||
      !cursor ||
      this.inputs.activeRouteConversationId !== conversationId ||
      this.inputs.activeConversationIdRef !== conversationId ||
      this.inputs.readyTranscriptConversationId !== conversationId ||
      this.inputs.transcriptRoot?.dataset.conversationId !== conversationId ||
      !this.inputs.sentinel ||
      !this.inputs.hydrationComplete ||
      this.inputs.manualUnreadGuard ||
      this.inputs.markReadPending ||
      !this.sentinelIntersecting ||
      !this.options.effects.isDocumentVisible() ||
      !this.options.effects.isWindowFocused()
    ) {
      return null;
    }
    return { conversationId, cursor };
  }

  private evaluateReadProof(): void {
    if (!this.started || this.disposed) return;
    const proof = this.proofConversation();
    if (!proof) return;
    const key = readKey(proof.conversationId, proof.cursor);
    if (
      this.acknowledgedReads.has(key) ||
      this.inFlightReads.has(key) ||
      this.failedReadTrigger.get(key) === this.meaningfulTrigger
    ) {
      return;
    }
    this.inFlightReads.add(key);
    void this.options
      .markRead(proof.conversationId, proof.cursor)
      .then(() => {
        this.resolvedReads.set(key, proof);
        this.settleResolvedReads();
      })
      .catch(() => {
        this.failedReadTrigger.set(key, this.meaningfulTrigger);
        this.inFlightReads.delete(key);
      });
  }

  private settleResolvedReads(): void {
    for (const [key, proof] of this.resolvedReads) {
      if (this.inputs.activeConversationId !== proof.conversationId) {
        this.resolvedReads.delete(key);
        this.inFlightReads.delete(key);
        continue;
      }
      if (this.inputs.markReadPending) continue;
      if (this.inputs.attentionCursor !== proof.cursor) {
        this.acknowledgedReads.add(key);
        this.failedReadTrigger.delete(key);
      } else {
        this.failedReadTrigger.set(key, this.meaningfulTrigger);
      }
      this.resolvedReads.delete(key);
      this.inFlightReads.delete(key);
    }
  }
}

export const createConversationActivityViewportRuntime = (
  options: CreateConversationActivityViewportRuntimeOptions,
): ConversationActivityViewportRuntime =>
  new ConversationActivityViewportOwner(options);

type UseConversationActivityViewportOptions = Readonly<{
  activity: Pick<
    UseConversationActivityResult,
    | "state"
    | "hasManualUnreadGuard"
    | "isMutationPending"
    | "markRead"
    | "resetViewEpoch"
  >;
  activeRouteConversationId: string | null;
  activeConversationId: string | null;
  activeConversationIdRef: RefObject<string | null>;
  readyTranscriptConversationIdRef: RefObject<string | null>;
  transcriptRootRef: RefObject<HTMLDivElement | null>;
  sentinelRef: RefObject<HTMLDivElement | null>;
  hydrationComplete: boolean;
  testEffects?: ConversationActivityViewportEffectsAdapter;
}>;

export function useConversationActivityViewport(
  options: UseConversationActivityViewportOptions,
): void {
  const snapshotInputs = (): ConversationActivityViewportInputs => {
    const conversationId = options.activeConversationId;
    const record = conversationId
      ? options.activity.state.byConversationId[conversationId]
      : undefined;
    return {
      activeRouteConversationId: options.activeRouteConversationId,
      activeConversationId: conversationId,
      activeConversationIdRef: options.activeConversationIdRef.current,
      readyTranscriptConversationId:
        options.readyTranscriptConversationIdRef.current,
      transcriptRoot: options.transcriptRootRef.current,
      sentinel: options.sentinelRef.current,
      hydrationComplete: options.hydrationComplete,
      attentionCursor: record?.canonical?.attention.cursor ?? null,
      manualUnreadGuard:
        options.activity.hasManualUnreadGuard(conversationId),
      markReadPending: conversationId
        ? options.activity.isMutationPending(conversationId, "mark_read")
        : false,
    };
  };
  const [runtime] = useState(() =>
    createConversationActivityViewportRuntime({
      inputs: snapshotInputs(),
      effects: options.testEffects ?? createBrowserEffectsAdapter(),
      markRead: options.activity.markRead,
      resetViewEpoch: options.activity.resetViewEpoch,
    }),
  );

  useLayoutEffect(() => {
    runtime.updateInputs(snapshotInputs());
  });
  useEffect(() => {
    runtime.start();
    return runtime.dispose;
  }, [runtime]);
}
