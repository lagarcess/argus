"use client";

import {
  createContext,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { CircleAlert, CircleHelp, LoaderCircle } from "lucide-react";

import { inlineFailureTextClass } from "@/lib/failure-treatment";
import type {
  ConversationActivityOperationLabel,
  ConversationActivityPresentation,
} from "@/lib/conversation-activity-state";

type ConversationActivityPresentationContextValue = Readonly<{
  selectPresentation: (
    conversationId: string | null | undefined,
  ) => ConversationActivityPresentation;
  selectAggregatePresentation: (
    conversationIds?: readonly string[],
  ) => ConversationActivityPresentation;
  selectOperationLabel: (
    conversationId: string | null | undefined,
  ) => ConversationActivityOperationLabel | null;
}>;

const ConversationActivityPresentationContext =
  createContext<ConversationActivityPresentationContextValue>({
    selectPresentation: () => "none",
    selectAggregatePresentation: () => "none",
    selectOperationLabel: () => null,
  });

export function ConversationActivityPresentationProvider({
  children,
  selectPresentation,
  selectAggregatePresentation,
  selectOperationLabel,
}: ConversationActivityPresentationContextValue & Readonly<{ children: ReactNode }>) {
  const value = useMemo(
    () => ({ selectPresentation, selectAggregatePresentation, selectOperationLabel }),
    [selectAggregatePresentation, selectOperationLabel, selectPresentation],
  );

  return (
    <ConversationActivityPresentationContext.Provider value={value}>
      {children}
    </ConversationActivityPresentationContext.Provider>
  );
}

export const useConversationActivityPresentation =
  (): ConversationActivityPresentationContextValue =>
    useContext(ConversationActivityPresentationContext);

type ActivityLabelDescriptor = Readonly<{
  key: string;
  defaultValue: string;
}>;

const ACTIVITY_LABELS: Record<
  Exclude<ConversationActivityPresentation, "none">,
  ActivityLabelDescriptor
> = {
  working: { key: "chat.activity.working", defaultValue: "Working" },
  needs_attention: {
    key: "chat.activity.needs_attention",
    defaultValue: "Needs attention",
  },
  needs_input: {
    key: "chat.activity.needs_input",
    defaultValue: "Needs your input",
  },
  new_activity: {
    key: "chat.activity.new_activity",
    defaultValue: "New activity",
  },
  manual_unread: {
    key: "chat.activity.manual_unread",
    defaultValue: "Marked unread",
  },
};

const OPERATION_LABELS: Record<
  ConversationActivityOperationLabel,
  ActivityLabelDescriptor
> = {
  queued: { key: "chat.activity.queued", defaultValue: "Queued" },
  working: ACTIVITY_LABELS.working,
  checking: {
    key: "chat.activity.checking",
    defaultValue: "Checking status",
  },
};

export const conversationActivityLabelDescriptor = (
  presentation: ConversationActivityPresentation,
  operationLabel: ConversationActivityOperationLabel | null = null,
): ActivityLabelDescriptor | null =>
  presentation === "none"
    ? null
    : presentation === "working" && operationLabel
      ? OPERATION_LABELS[operationLabel]
      : ACTIVITY_LABELS[presentation];

type ConversationActivityIndicatorProps = Readonly<{
  presentation: ConversationActivityPresentation;
  compact?: boolean;
  className?: string;
}>;

export function ConversationActivityIndicator({
  presentation,
  compact = false,
  className = "",
}: ConversationActivityIndicatorProps) {
  if (presentation === "none") return null;

  const iconSize = compact ? "h-3 w-3" : "h-4 w-4";

  return (
    <span
      aria-hidden="true"
      data-conversation-activity={presentation}
      className={`inline-flex shrink-0 items-center justify-center ${className}`}
    >
      {presentation === "working" ? (
        <LoaderCircle
          className={`${iconSize} animate-spin text-black/45 [animation-duration:1.8s] motion-reduce:animate-none dark:text-white/55`}
        />
      ) : presentation === "needs_attention" ? (
        <CircleAlert className={`${iconSize} ${inlineFailureTextClass}`} />
      ) : presentation === "needs_input" ? (
        <CircleHelp className={`${iconSize} text-[#6f8eb4] dark:text-[#9ab9dc]`} />
      ) : (
        <span
          data-activity-dot="true"
          className={`${compact ? "h-2 w-2" : "h-2.5 w-2.5"} rounded-full border border-[#f4f4f4] bg-[#70a38d] dark:border-[#191c1f] dark:bg-[#9bc6b4]`}
        />
      )}
    </span>
  );
}
