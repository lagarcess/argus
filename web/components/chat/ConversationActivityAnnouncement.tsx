"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { UseConversationActivityResult } from "@/components/chat/useConversationActivity";
import type {
  ConversationActivityAnnouncement as ActivityTransition,
  ConversationActivityPresentation,
} from "@/lib/conversation-activity-state";

type ActivityAnnouncementDescriptor = Readonly<{
  key: string;
  defaultValue: string;
  title: string;
}>;

type ActivityTranslation = (
  key: string,
  options: Readonly<{ defaultValue: string; title: string }>,
) => string;

type ActivityAnnouncementOwner = Pick<
  UseConversationActivityResult,
  | "acknowledgeAnnouncement"
  | "getAnnouncement"
  | "selectPresentation"
>;

type ConsumedActivityAnnouncement = Readonly<{
  conversationId: string;
  key: string;
  message: string;
}>;

const ANNOUNCEMENT_COPY: Record<
  Exclude<ConversationActivityPresentation, "manual_unread" | "none">,
  Readonly<{ key: string; defaultValue: string }>
> = {
  working: {
    key: "chat.activity.announce_working",
    defaultValue: "Argus is working in {{title}}.",
  },
  needs_attention: {
    key: "chat.activity.announce_needs_attention",
    defaultValue: "{{title}} needs attention.",
  },
  needs_input: {
    key: "chat.activity.announce_needs_input",
    defaultValue: "{{title}} needs your input.",
  },
  new_activity: {
    key: "chat.activity.announce_new_activity",
    defaultValue: "New activity is ready in {{title}}.",
  },
};

export const conversationActivityAnnouncementDescriptor = (
  presentation: ActivityTransition["presentation"],
  title: string,
): ActivityAnnouncementDescriptor | null => {
  if (presentation === "manual_unread") return null;
  return { ...ANNOUNCEMENT_COPY[presentation], title };
};

export const consumeConversationActivityAnnouncement = ({
  activity,
  conversationId,
  title,
  translate,
}: Readonly<{
  activity: Pick<
    ActivityAnnouncementOwner,
    "acknowledgeAnnouncement" | "getAnnouncement"
  >;
  conversationId: string;
  title: string;
  translate: ActivityTranslation;
}>): ConsumedActivityAnnouncement | null => {
  const transition = activity.getAnnouncement(conversationId);
  if (!transition) return null;
  const descriptor = conversationActivityAnnouncementDescriptor(
    transition.presentation,
    title,
  );
  activity.acknowledgeAnnouncement(conversationId, transition.key);
  if (!descriptor) return null;
  return {
    conversationId,
    key: transition.key,
    message: translate(descriptor.key, descriptor),
  };
};

export function ConversationActivityLiveRegion({
  announcementKey,
  message,
}: Readonly<{ announcementKey: string; message: string }>) {
  return (
    <span
      data-testid="conversation-activity-announcement"
      className="sr-only"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span key={announcementKey}>{message}</span>
    </span>
  );
}

export default function ConversationActivityAnnouncement({
  activity,
  conversationId,
  title,
  enabled = true,
}: Readonly<{
  activity: ActivityAnnouncementOwner;
  conversationId: string | null;
  title: string;
  enabled?: boolean;
}>) {
  const { t } = useTranslation();
  const [consumed, setConsumed] =
    useState<ConsumedActivityAnnouncement | null>(null);
  const transition = enabled
    ? activity.getAnnouncement(conversationId)
    : null;
  const presentation = enabled
    ? activity.selectPresentation(conversationId)
    : "none";

  useEffect(() => {
    if (!enabled || !conversationId) {
      setConsumed(null);
      return;
    }
    if (transition) {
      setConsumed(
        consumeConversationActivityAnnouncement({
          activity,
          conversationId,
          title,
          translate: t,
        }),
      );
      return;
    }
    if (
      presentation === "none" ||
      consumed?.conversationId !== conversationId
    ) {
      setConsumed(null);
    }
  }, [activity, consumed?.conversationId, conversationId, enabled, presentation, t, title, transition]);

  return (
    <ConversationActivityLiveRegion
      announcementKey={consumed?.key ?? "none"}
      message={consumed?.message ?? ""}
    />
  );
}
