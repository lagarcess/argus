"use client";

import React, { useState } from "react";
import { ComputationComparePanel } from "./ComputationCompare";
import { continueComputedAnswer } from "@/lib/computations-api";
import type { ToolTranslator } from "@/lib/tool-result-card";

const ACTION_CLASS =
  "inline-flex min-h-11 items-center rounded-full border border-black/10 px-4 text-[13px] text-black/70 transition-colors hover:bg-black/[0.03] disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:text-white/70 dark:hover:bg-white/[0.05]";

/**
 * What a computed answer offers beside its card: compare it with another result
 * of the same kind, and continue it in a new chat that carries only this
 * result. Both are free. Continue appears only when the caller can open the new
 * chat, which is only for a registered owner.
 */
export default function ComputedAnswerActions({ conversationId, messageId, kind, onOpenConversation, t, locale }: {
  conversationId: string; messageId: string; kind: string;
  onOpenConversation?: (conversationId: string) => void; t: ToolTranslator; locale: string;
}) {
  const [comparing, setComparing] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [failed, setFailed] = useState(false);
  const continueResult = async () => {
    setContinuing(true);
    setFailed(false);
    try {
      const result = await continueComputedAnswer({ conversation_id: conversationId, message_id: messageId });
      onOpenConversation?.(result.conversation.id);
    } catch {
      setFailed(true);
    } finally {
      setContinuing(false);
    }
  };
  return <div data-computed-answer-actions className="w-full min-w-0">
    <div className="flex flex-wrap gap-2">
      <button type="button" data-compute-action="compare" aria-expanded={comparing} onClick={() => setComparing((open) => !open)} className={ACTION_CLASS}>
        {t(comparing ? "tools.compute.compare_close" : "tools.compute.compare")}
      </button>
      {onOpenConversation ? <button type="button" data-compute-action="continue" disabled={continuing} onClick={() => { void continueResult(); }} className={ACTION_CLASS}>
        {t(continuing ? "tools.compute.continuing" : "tools.compute.continue")}
      </button> : null}
    </div>
    {failed ? <p role="alert" className="mt-2 text-xs text-rose-700 dark:text-rose-300">{t("tools.compute.continue_failed")}</p> : null}
    {comparing ? <ComputationComparePanel source={{ conversationId, messageId, kind }} t={t} locale={locale} /> : null}
  </div>;
}
