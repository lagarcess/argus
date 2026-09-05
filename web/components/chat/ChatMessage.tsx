"use client";

import { useState, useRef, useEffect } from "react";
import { ThumbsUp, ThumbsDown, MoreHorizontal, Copy, MessageSquareWarning, RotateCcw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useTranslation } from "react-i18next";
import StrategyResultCard from "./StrategyResultCard";
import StrategyConfirmationCard from "./StrategyConfirmationCard";
import BacktestJobCard from "./BacktestJobCard";
import DiscoverySourcesPanel from "./DiscoverySourcesPanel";
import MemoryRecallNote from "./MemoryRecallNote";
import { RetestReceipt } from "./RetestReceipt";
import { RETEST_ACTION_TYPE } from "@/lib/chat-retest";
import NextMoveRow, {
  NextMoveDetail,
  NextMoveSeparator,
  NextMoveTicker,
  NextMoveTitle,
} from "./NextMoveRow";
import {
  nextExperimentAction,
  nextExperimentReasonText,
} from "@/lib/chat-next-experiments";
import {
  type ChatActionOption,
  type ChatMention,
  type ConfirmationDirectEditPayload,
  Message,
} from "./types";
import type { DecisionState } from "@/lib/argus-api";
import { normalizeAssistantDisplayText } from "@/lib/chat-display-text";
import {
  confirmationCardCopyText,
  resultCardCopyText,
} from "@/lib/chat-card-copy-text";
import { confirmationCardViewModel } from "@/lib/confirmation-card-view-model";
import { resultCardViewModel } from "@/lib/result-card-view-model";
import { resultBreakdownText, resultQuickTakeText } from "@/lib/result-readout-display";
import { writeClipboardText } from "@/lib/clipboard";
import { isRetryAction } from "@/lib/chat-retry-actions";
import {
  recoveryDisplayCopyText,
  recoveryDisplayText,
} from "@/lib/chat-recovery-display";
import { feedbackContextForMessage } from "@/lib/chat-message-feedback-context";
import { Tooltip } from "@/components/ui/Tooltip";
import FailureNotice from "./FailureNotice";
import {
  retryableNoticeBodyClass,
  retryableNoticeContainerClass,
  retryableNoticeIconClass,
  retryableNoticeRetryPillClass,
} from "@/lib/failure-treatment";
import GuestArtifactHint from "@/components/guest/GuestArtifactHint";
import { useResponsiveLayout } from "@/components/layout/useResponsiveLayout";
import { actionHasCardScopedOwnership } from "@/lib/chat-action-ownership";
import { confirmationPeriodAdjustmentText } from "@/lib/confirmation-period-adjustment";
import { confirmationBenchmarkAdjustmentText } from "@/lib/confirmation-benchmark-adjustment";
import { confirmationEditDisclosureText } from "@/lib/confirmation-edit-disclosure";
import { discoveryEscalationCopyPlan } from "@/lib/chat-discovery-escalation";
import { EntityToken } from "./entity-token";
import { messageMentionPieces } from "./mention-rendering";


type ChatMessageProps = {
  message: Message;
  onAction?: (action: ChatActionOption) => void;
  onDirectEdit?: (
    confirmationId: string,
    edit: ConfirmationDirectEditPayload,
  ) => Promise<void>;
  onFeedback?: (type: "bug" | "feature" | "general" | "rating", context: Record<string, unknown>, rating?: "positive" | "negative") => void;
  onToast?: (message: string, variant?: "neutral" | "error") => void;
  isLatest?: boolean;
  isStreaming?: boolean;
  conversationId?: string | null;
  nextMovesEnabled?: boolean;
  turnInFlight?: boolean;
  isGuest?: boolean;
  canSaveDecision?: boolean;
  memoryProposalEnabled?: boolean;
  onDecisionUnavailable?: (artifactId: string) => void;
  onDecisionSaved?: (decisionState: DecisionState) => void;
  onRequestSearchUpgrade?: () => void;
  resumeDecisionArtifactId?: string | null;
  onDecisionResumeHandled?: () => void;
};

const retryIconButtonClass =
  "inline-flex items-center justify-center rounded-full text-black/60 transition-all duration-200 hover:bg-black/5 hover:text-black dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white";

export default function ChatMessage({
  message,
  onAction,
  onDirectEdit,
  onFeedback,
  onToast,
  isLatest,
  isStreaming,
  conversationId,
  nextMovesEnabled = true,
  turnInFlight = false,
  isGuest = false,
  canSaveDecision = true,
  memoryProposalEnabled = false,
  onDecisionUnavailable,
  onDecisionSaved,
  onRequestSearchUpgrade,
  resumeDecisionArtifactId,
  onDecisionResumeHandled,
}: ChatMessageProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language ?? "en";
  const { isBelowTablet } = useResponsiveLayout();
  const isUser = message.role === "user";
  const [rating, setRating] = useState<"positive" | "negative" | null>(null);
  const [showOptions, setShowOptions] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [anchorSourceIndex, setAnchorSourceIndex] = useState<number | null>(
    null,
  );
  const [menuPosition, setMenuPosition] = useState<"top" | "bottom">("bottom");
  const optionsRef = useRef<HTMLDivElement>(null);
  const selectedFeedbackClass =
    "hover:bg-black/5 dark:hover:bg-white/10 text-[#191c1f] dark:text-white";
  const idleFeedbackClass =
    "hover:bg-black/5 dark:hover:bg-white/10 text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white";
  const selectedFeedbackIconClass = "fill-current";
  const feedbackContext = (extra: Record<string, string | number | boolean> = {}) =>
    feedbackContextForMessage(message, conversationId, extra);

  const toggleOptions = (e: React.MouseEvent) => {
    if (!showOptions) {
      const buttonRect = e.currentTarget.getBoundingClientRect();
      // If the button is too close to the bottom of the screen (e.g. within 160px), map the popup upwards
      if (buttonRect.bottom + 160 > window.innerHeight) {
        setMenuPosition("top");
      } else {
        setMenuPosition("bottom");
      }
      setShowOptions(true);
    } else {
      setShowOptions(false);
    }
  };

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (optionsRef.current && !optionsRef.current.contains(event.target as Node)) {
        setShowOptions(false);
      }
    }

    function handleScroll() {
      setShowOptions(false);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setShowOptions(false);
      }
    }

    if (showOptions) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
      // Use capture phase to ensure we catch the scroll event from the inner container natively
      window.addEventListener("scroll", handleScroll, true);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", handleScroll, true);
    };
  }, [showOptions]);

  const normalizeCopyText = (text: string) =>
    isUser ? text : normalizeAssistantDisplayText(text);

  const handleRating = (newRating: "positive" | "negative") => {
    if (rating === newRating) {
      setRating(null);
    } else {
      setRating(newRating);
      onFeedback?.("rating", feedbackContext(), newRating);
    }
  };

  const getCopyText = () => {
    if (!isUser && message.contentPresentation === "result_readout") {
      return resultQuickTakeText(message.resultReadoutFacts, t, i18n.resolvedLanguage ?? i18n.language ?? "en");
    }
    if (!isUser) {
      const localizedRecovery = recoveryDisplayCopyText(message.recoveryDisplay, t, locale);
      if (localizedRecovery) {
        return normalizeCopyText(localizedRecovery);
      }
    }
    // Copy reads the card's own view model. Deriving it from the payload
    // again is what put backend English on a Spanish workspace (#509).
    if (message.kind === "strategy_result" && message.result) {
      return normalizeCopyText(
        resultCardCopyText(
          resultCardViewModel(message.result, { t, locale }),
          t,
        ),
      );
    }
    if (message.kind === "strategy_confirmation" && message.confirmation) {
      return normalizeCopyText(
        confirmationCardCopyText(
          confirmationCardViewModel(message.confirmation, t, locale),
          t,
          locale,
        ),
      );
    }
    if (message.contentPresentation === "result_breakdown") {
      return resultBreakdownText(null, t, locale);
    }
    return normalizeCopyText(message.content ?? "");
  };

  const handleCopy = async (text = getCopyText()) => {
    const copied = await writeClipboardText(text);
    onToast?.(
      t(copied ? "chat.copy_success" : "chat.copy_failed"),
      copied ? "neutral" : "error",
    );
  };

  const getDisplayContent = () => {
    if (!isUser && message.contentPresentation === "result_readout") {
      return resultQuickTakeText(message.resultReadoutFacts, t, i18n.resolvedLanguage ?? i18n.language ?? "en");
    }
    if (!isUser && message.kind === "strategy_result") {
      return resultQuickTakeText(message.result?.readoutFacts, t, i18n.resolvedLanguage ?? i18n.language ?? "en");
    }
    const content = message.content ?? "";
    if (!isUser && message.recoveryDisplay) {
      const recovered = recoveryDisplayText(message.recoveryDisplay, t, locale);
      if (recovered.trim()) {
        return recovered;
      }
    }
    if (!isUser && message.contentPresentation === "result_breakdown") {
      return resultBreakdownText(null, t, i18n.resolvedLanguage ?? i18n.language ?? "en");
    }
    return isUser ? content : normalizeAssistantDisplayText(content);
  };

  const actionLabel = (action: ChatActionOption) =>
    action.labelKey
      ? t(action.labelKey, {
          defaultValue: action.label,
          ...((action.payload ?? {}) as Record<string, unknown>),
        })
      : action.label;
  const retryAction = message.actions?.find(isRetryAction);
  const userRecoveryText =
    isUser && message.recoveryDisplay
      ? recoveryDisplayText(message.recoveryDisplay, t, locale).trim()
      : "";
  const footerMessageActions = (message.actions ?? []).filter(
    (action) => !isRetryAction(action) && !actionHasCardScopedOwnership(action),
  );
  const shouldShowAssistantFooter = !isUser && !isStreaming;
  // Next moves answer the newest question only. Older groups are settled by the
  // reply that followed them, so they stop rendering rather than staying
  // tappable — the guard the floating composer strip used to provide.
  const showNextMoveRows =
    shouldShowAssistantFooter &&
    Boolean(isLatest) &&
    nextMovesEnabled &&
    footerMessageActions.length > 0;
  const footerVisibilityClass =
    isLatest || rating || showOptions || Boolean(retryAction)
      ? "opacity-100"
      : "pointer-events-none opacity-0 group-hover:pointer-events-auto group-hover:opacity-100 focus-within:pointer-events-auto focus-within:opacity-100";
  const displayContent = getDisplayContent();
  // Chips carry domains and the drawer owns the list; zero sources is the
  // ungrounded marker (derived, never asserted). Canon: DESIGN.md §11.
  const discoverySourcesLineText =
    isUser ||
    !message.discovery ||
    message.discovery.sources.length > 0
      ? ""
      : t("chat.discovery_results.unsourced_line", {
          defaultValue: "From general knowledge, not a current search",
        });
  // Localized heading chrome for latest-result fact answers, driven by the
  // typed fact key. Unknown keys render no heading.
  const factHeadingLabel = message.resultFactHeadingKey
    ? t(`chat.result_followup.headings.${message.resultFactHeadingKey}`, "")
    : "";
  const confirmationPeriodLeadIn = confirmationPeriodAdjustmentText(
    message.confirmation?.period_adjustment,
    (key, options) => t(key, options),
    i18n.resolvedLanguage ?? i18n.language ?? "en",
  );
  const confirmationBenchmarkLeadIn = confirmationBenchmarkAdjustmentText(
    message.confirmation?.benchmark_adjustment,
    (key, options) => t(key, options),
  );
  const confirmationEditDisclosureLeadIn = confirmationEditDisclosureText(
    message.confirmation?.edit_disclosure,
    t,
  );

  if (isUser && message.kind === "action") {
    const actionText =
      displayContent ||
      (message.selectedAction ? actionLabel(message.selectedAction) : "");
    const showRetestReceipt =
      Boolean(message.retestReceipt) ||
      (message.selectedAction?.type === RETEST_ACTION_TYPE &&
        message.retestReceiptPending === true);
    return (
      <div className="flex w-full flex-col items-end animate-in fade-in slide-in-from-bottom-2 duration-300">
        {showRetestReceipt ? (
          <RetestReceipt
            receipt={message.retestReceipt ?? null}
            actionLabel={actionText}
            pending={message.retestReceiptPending === true}
          />
        ) : (
          <div className="max-w-[85%] rounded-full border border-black/10 bg-black/[0.03] px-4 py-2.5 text-[14px] font-medium leading-[1.45] text-black/75 dark:border-white/12 dark:bg-white/[0.06] dark:text-white/75">
            {actionText}
          </div>
        )}
        <UserTurnRecovery
          recoveryText={userRecoveryText}
          retryAction={retryAction}
          retryLabel={retryAction ? actionLabel(retryAction) : ""}
          onAction={onAction}
        />
      </div>
    );
  }

  if (isUser) {
    return (
      <div className="flex w-full flex-col items-end animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="max-w-[85%] bg-black/5 dark:bg-white/10 text-black dark:text-white px-5 py-3.5 rounded-[24px] rounded-br-sm text-[16px] leading-[1.5] tracking-[0.24px] font-normal">
          <UserMessageContent content={displayContent} mentions={message.mentions ?? []} />
        </div>
        <UserTurnRecovery
          recoveryText={userRecoveryText}
          retryAction={retryAction}
          retryLabel={retryAction ? actionLabel(retryAction) : ""}
          onAction={onAction}
        />
      </div>
    );
  }

  return (
    <div className="flex w-full justify-start animate-in fade-in slide-in-from-bottom-2 duration-300 group relative">
      {!isUser && !isStreaming && (
        <Tooltip content={t('chat.copy_plaintext')} side="left" delay={150}>
          <button
            onClick={() => {
              void handleCopy();
            }}
            className="absolute -left-10 top-1 opacity-0 group-hover:opacity-40 hover:!opacity-100 transition-opacity p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-black dark:text-white"
            aria-label={t('chat.copy_plaintext')}
          >
            <Copy className="w-4 h-4" />
          </button>
        </Tooltip>
      )}
      <div className="flex flex-col max-w-[85%]">
        <div className="flex flex-col mt-1.5">
          {message.kind === "strategy_result" && message.result && !message.isLoadingResult ? (
            <div className="flex w-full max-w-[min(100%,660px)] flex-col gap-4">
              <StrategyResultCard
                result={message.result}
                onAction={onAction}
                canSaveDecision={canSaveDecision}
                memoryProposalEnabled={memoryProposalEnabled}
                onDecisionUnavailable={onDecisionUnavailable}
                onDecisionSaved={onDecisionSaved}
                resumeDecisionArtifactId={resumeDecisionArtifactId}
                onDecisionResumeHandled={onDecisionResumeHandled}
              />
              {isGuest ? <GuestArtifactHint kind="result" /> : null}
              {displayContent && (
                <ResultReadout
                  content={displayContent}
                  label={t("chat.result_readout.quick_take", "Quick take")}
                />
              )}
            </div>
          ) : message.kind === "backtest_job" && message.backtestJob ? (
            <div className="w-full max-w-[min(100%,660px)]">
              <BacktestJobCard
                job={message.backtestJob}
                canRetry={Boolean(retryAction)}
                failureMessage={displayContent}
                onRetry={
                  retryAction ? () => onAction?.(retryAction) : undefined
                }
                retryLabel={retryAction ? actionLabel(retryAction) : undefined}
              />
            </div>
          ) : message.kind === "strategy_confirmation" && message.confirmation ? (
            <div className="flex w-full max-w-[min(100%,660px)] flex-col gap-3">
              {confirmationPeriodLeadIn ? (
                <p className="text-[15px] leading-[1.55] tracking-[0.2px] text-black/75 dark:text-white/75">
                  {confirmationPeriodLeadIn}
                </p>
              ) : null}
              {confirmationBenchmarkLeadIn ? (
                <p className="text-[15px] leading-[1.55] tracking-[0.2px] text-black/75 dark:text-white/75">
                  {confirmationBenchmarkLeadIn}
                </p>
              ) : null}
              {confirmationEditDisclosureLeadIn ? (
                <p
                  data-testid="confirmation-edit-disclosure"
                  className="text-[15px] leading-[1.55] tracking-[0.2px] text-black/75 dark:text-white/75"
                >
                  {confirmationEditDisclosureLeadIn}
                </p>
              ) : null}
              <StrategyConfirmationCard
                confirmation={message.confirmation}
                disabled={turnInFlight}
                onAction={onAction}
                onDirectEdit={
                  onDirectEdit && message.confirmation.confirmation_id
                    ? (edit) =>
                        onDirectEdit(message.confirmation!.confirmation_id!, edit)
                    : undefined
                }
              />
              {isGuest ? <GuestArtifactHint kind="confirmation" /> : null}
            </div>
          ) : message.contentPresentation === "result_readout" ? (
            <ResultReadout content={displayContent} label={t("chat.result_readout.quick_take", "Quick take")} />
          ) : message.contentPresentation === "result_breakdown" && displayContent.trim() ? (
            <ResultBreakdown
              ariaLabel={t("chat.result_breakdown.aria_label", "Result breakdown")}
              content={displayContent}
              label={t("chat.result_breakdown.label", "Breakdown")}
            />
          ) : !isUser && message.assistantRecoveryCode ? (
            // Infrastructure failure is visibly a failure: no result chrome,
            // no normal-answer bubble (issue #249).
            <div
              role="status"
              className={`${retryableNoticeContainerClass} max-w-[min(100%,660px)]`}
            >
              <MessageSquareWarning
                className={retryableNoticeIconClass}
                aria-hidden="true"
              />
              <div className={retryableNoticeBodyClass}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {displayContent}
                </ReactMarkdown>
              </div>
              {retryAction ? (
                <button
                  type="button"
                  onClick={() => onAction?.(retryAction)}
                  className={retryableNoticeRetryPillClass}
                >
                  {actionLabel(retryAction)}
                </button>
              ) : null}
            </div>
          ) : !isUser &&
            message.recoveryDisplay?.kind === "artifact_action_recovery" ? (
            // A rejected/inactive action is still a failure statement; it
            // must not read as an ordinary answer, only quieter than amber.
            <FailureNotice
              className="max-w-[min(100%,660px)]"
              testId="artifact-action-failure-notice"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {displayContent}
              </ReactMarkdown>
            </FailureNotice>
          ) : (
            <div className="text-black dark:text-white text-[16px] leading-[1.6] tracking-[0.24px] prose dark:prose-invert max-w-none">
              {factHeadingLabel && (
                <div className="argus-result-section-label">{factHeadingLabel}</div>
              )}
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {displayContent}
              </ReactMarkdown>
            </div>
          )}

          {!isUser && !isStreaming && message.memoryRecalls?.length ? (
            <MemoryRecallNote recalls={message.memoryRecalls} />
          ) : null}
          {!isUser && !isStreaming && message.discovery && (
            <div className="mt-3 flex w-full max-w-[min(100%,660px)] flex-col gap-2">
              <div className="flex flex-col divide-y divide-black/8 dark:divide-white/8">
                {message.discovery.candidates.map((candidate) => {
                  const sendText = t("chat.discovery_results.test_candidate", {
                    symbol: candidate.symbol,
                    defaultValue: "Backtest {{symbol}}",
                  });
                  // One row vocabulary: the same verb the rail's rows use,
                  // with the name leading and the ticker as its badge. The
                  // sent text stays the backend-owned action string.
                  const testVerb = t("chat.next_experiments.test_verb", {
                    defaultValue: "Test",
                  });
                  const hasName =
                    Boolean(candidate.name) && candidate.name !== candidate.symbol;
                  // One chip per row: the first corroborating source. Cheap
                  // rows carry no indices, so they stay chipless by shape.
                  const chipIndex = candidate.source_indices?.[0];
                  const chipSource =
                    chipIndex === undefined
                      ? undefined
                      : message.discovery?.sources[chipIndex];
                  return (
                    <NextMoveRow
                      key={candidate.symbol}
                      ariaLabel={sendText}
                      disabled={turnInFlight}
                      onClick={() =>
                        onAction?.({
                          type: "select_discovery_candidate",
                          label: sendText,
                          labelKey: "chat.discovery_results.test_candidate",
                          value: sendText,
                          payload: {
                            symbol: candidate.symbol,
                            name: candidate.name,
                            asset_class: candidate.asset_class,
                          },
                        })
                      }
                    >
                      <NextMoveTitle>
                        {testVerb}
                        {hasName ? ` ${candidate.name}` : ""}{" "}
                        <NextMoveTicker>{candidate.symbol}</NextMoveTicker>
                      </NextMoveTitle>
                      {candidate.reason_text ? (
                        <>
                          <NextMoveSeparator>·</NextMoveSeparator>
                          <NextMoveDetail>{candidate.reason_text}</NextMoveDetail>
                        </>
                      ) : null}
                      {chipSource ? (
                        // Plain span: interactive content is invalid inside
                        // the row button; the sources button is the keyboard path.
                        <span
                          onClick={(event) => {
                            event.stopPropagation();
                            setAnchorSourceIndex(chipIndex ?? null);
                            setShowSources(true);
                          }}
                          className="ms-1.5 inline-flex translate-y-[-1px] cursor-pointer items-center rounded-full border border-black/10 px-1.5 py-px align-middle text-[11px] leading-[1.4] text-black/45 transition-colors hover:border-black/25 hover:text-black/70 dark:border-white/12 dark:text-white/45 dark:hover:border-white/30 dark:hover:text-white/75"
                        >
                          {chipSource.domain}
                        </span>
                      ) : null}
                    </NextMoveRow>
                  );
                })}
                {message.discovery.sources.length === 0 &&
                message.discovery.can_request_search &&
                isLatest ? (
                  (() => {
                    const searchLabel = t(
                      "chat.discovery_results.search_current",
                      { defaultValue: "Search for current results" },
                    );
                    const copyPlan = discoveryEscalationCopyPlan(
                      message.discovery,
                    );
                    const assetKind = t(copyPlan.assetKindKey, {
                      defaultValue: copyPlan.assetKindDefaultValue,
                    });
                    // Restate the relationship: peer/comparison query_summary
                    // is bare symbols, and "search for: AAPL" reads as a test.
                    const searchSendText = t(
                      copyPlan.messageKey,
                      {
                        query: copyPlan.query,
                        assetKind,
                        defaultValue: copyPlan.messageDefaultValue,
                      },
                    );
                    return (
                      <NextMoveRow
                        ariaLabel={searchLabel}
                        disabled={turnInFlight}
                        onClick={() =>
                          // Typeless: a typed option is validated against the
                          // latest turn's options and rejected as stale.
                          onAction?.({
                            label: searchSendText,
                            value: searchSendText,
                          })
                        }
                      >
                        <NextMoveTitle>{searchLabel}</NextMoveTitle>
                      </NextMoveRow>
                    );
                  })()
                ) : null}
              </div>
              {isGuest &&
              isLatest &&
              message.discovery.sources.length === 0 &&
              message.discovery.can_request_search === false &&
              onRequestSearchUpgrade ? (
                // Upsell on appetite, never on apology: this renders only on
                // the honest exhausted answer, where the hidden search row sat.
                <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5 rounded-[14px] border border-[#5ba897]/25 bg-[#5ba897]/[0.08] px-3 py-2.5">
                  <p className="min-w-0 text-[13px] leading-[1.45] text-[#3f6658] dark:text-[#9fccbd]">
                    {t("chat.discovery_results.allowance_banner", {
                      defaultValue: "Grounded search allowance used",
                    })}
                  </p>
                  <button
                    type="button"
                    onClick={onRequestSearchUpgrade}
                    className="shrink-0 rounded-full border border-[#5ba897]/40 px-3 py-1.5 text-[13px] font-medium text-[#3f6658] transition-colors hover:bg-[#5ba897]/15 dark:text-[#b4d5c8] dark:hover:bg-[#5ba897]/20"
                  >
                    {t("chat.discovery_results.allowance_banner_cta", {
                      defaultValue: "Sign in for more searches",
                    })}
                  </button>
                </div>
              ) : null}
              {discoverySourcesLineText ||
              message.discovery.sources.length > 0 ? (
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-t border-black/8 pt-2 dark:border-white/8">
                  {discoverySourcesLineText ? (
                    <p className="min-w-0 text-[12px] leading-[1.5] tracking-[0.2px] text-black/50 [overflow-wrap:anywhere] dark:text-white/50">
                      {discoverySourcesLineText}
                    </p>
                  ) : null}
                  {message.discovery.sources.length > 0 ? (
                    <button
                      type="button"
                      onClick={() => setShowSources(true)}
                      className="relative z-10 shrink-0 text-[12px] leading-[1.5] tracking-[0.2px] text-black/50 underline-offset-2 transition-colors after:absolute after:inset-x-0 after:top-1/2 after:h-11 after:min-w-11 after:-translate-y-1/2 after:content-[''] hover:text-black/80 hover:underline dark:text-white/50 dark:hover:text-white/80"
                    >
                      {t("chat.discovery_results.sources_panel_open", {
                        count: message.discovery.sources.length,
                        defaultValue: "{{count}} sources ›",
                        defaultValue_one: "{{count}} source ›",
                      })}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          )}

          {/* One sources surface for every rail shape: the model never writes
              a citation line, and this renders only what the backend sidecar
              carried. */}
          {!message.discovery && (message.researchSources?.length ?? 0) > 0 ? (
            <div className="mt-2 flex w-full max-w-[min(100%,660px)]">
              <button
                type="button"
                onClick={() => setShowSources(true)}
                data-testid="research-sources-open"
                className="relative z-10 shrink-0 text-[12px] leading-[1.5] tracking-[0.2px] text-black/50 underline-offset-2 transition-colors after:absolute after:inset-x-0 after:top-1/2 after:h-11 after:min-w-11 after:-translate-y-1/2 after:content-[''] hover:text-black/80 hover:underline dark:text-white/50 dark:hover:text-white/80"
              >
                {t("chat.discovery_results.sources_panel_open", {
                  count: message.researchSources?.length ?? 0,
                  defaultValue: "{{count}} sources ›",
                  defaultValue_one: "{{count}} source ›",
                })}
              </button>
            </div>
          ) : null}

          {!message.discovery &&
          showSources &&
          (message.researchSources?.length ?? 0) > 0 ? (
            <DiscoverySourcesPanel
              onClose={() => {
                setShowSources(false);
                setAnchorSourceIndex(null);
              }}
              sidecar={{
                sources: message.researchSources ?? [],
                retrieved_at: "",
              }}
            />
          ) : null}

          {message.discovery && showSources ? (
            <DiscoverySourcesPanel
              onClose={() => {
                setShowSources(false);
                setAnchorSourceIndex(null);
              }}
              sidecar={message.discovery}
              anchorIndex={anchorSourceIndex}
            />
          ) : null}

          {/* Try next rows are the sanctioned next-move surface for any
              message that carries them (results, grounded knowledge answers);
              only mid-turn composition suppresses them. */}
          {shouldShowAssistantFooter &&
            Boolean(isLatest) &&
            !turnInFlight &&
            (message.nextExperiments?.length ?? 0) > 0 && (
              <section
                aria-label={t("chat.next_experiments.section", "Try next")}
                className="mt-5 flex w-full max-w-[min(100%,660px)] flex-col"
              >
                <div className="argus-result-section-label">
                  {t("chat.next_experiments.section", "Try next")}
                </div>
                <div className="flex w-full flex-col divide-y divide-black/8 dark:divide-white/8">
                  {(message.nextExperiments ?? []).map((row, rowIndex) => {
                    const rowLabel = t(row.labelKey, row.label);
                    // Narrow screens read the backend's short form; the clamp
                    // below is only a safety net, never a single-line ellipsis.
                    const narrowLabel =
                      isBelowTablet && row.labelShortKey
                        ? t(row.labelShortKey, row.labelShort ?? row.label)
                        : rowLabel;
                    // One result-level reason; captioning every row repeats it.
                    const whyText =
                      rowIndex === 0 ? nextExperimentReasonText(row.why, t, locale) : "";
                    return (
                      <NextMoveRow
                        key={row.kind}
                        ariaLabel={rowLabel}
                        disabled={turnInFlight}
                        onClick={() =>
                          onAction?.(
                            nextExperimentAction(
                              row,
                              rowLabel,
                              message.result?.runId,
                            ),
                          )
                        }
                      >
                        <NextMoveTitle>
                          {row.labelParts
                            ? row.labelParts.map((part, partIndex) =>
                                part.type === "ticker" ? (
                                  <span key={partIndex}>
                                    {" "}
                                    <NextMoveTicker>{part.value}</NextMoveTicker>
                                  </span>
                                ) : (
                                  <span key={partIndex}>{part.value}</span>
                                ),
                              )
                            : narrowLabel}
                        </NextMoveTitle>
                        {row.detail ? (
                          <>
                            <NextMoveSeparator>·</NextMoveSeparator>
                            <NextMoveDetail>{row.detail}</NextMoveDetail>
                          </>
                        ) : null}
                        {whyText ? (
                          <>
                            <NextMoveSeparator>·</NextMoveSeparator>
                            <NextMoveDetail>{whyText}</NextMoveDetail>
                          </>
                        ) : null}
                      </NextMoveRow>
                    );
                  })}
                </div>
              </section>
            )}

          {showNextMoveRows && (
            <div className="mt-2 flex w-full max-w-[min(100%,660px)] flex-col divide-y divide-black/8 dark:divide-white/8">
              {footerMessageActions.map((action) => (
                <NextMoveRow
                  key={action.id ?? action.type ?? action.label}
                  onClick={() => onAction?.(action)}
                >
                  <NextMoveTitle>{actionLabel(action)}</NextMoveTitle>
                </NextMoveRow>
              ))}
            </div>
          )}

          {shouldShowAssistantFooter && (
            <div className="flex items-start justify-end gap-4 mt-2">
              <div
                className={`relative flex shrink-0 items-center gap-1.5 transition-opacity ${footerVisibilityClass}`}
                ref={optionsRef}
                onBlur={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                    setShowOptions(false);
                  }
                }}
              >
                <Tooltip content={t('chat.good_response')} side="top" delay={150}>
                  <button
                    className={`p-1.5 rounded-full transition-all duration-200 group/thumb ${ rating === "positive" ? selectedFeedbackClass : idleFeedbackClass }`}
                    aria-label={t('chat.good_response')}
                    onClick={() => handleRating("positive")}
                  >
                    <ThumbsUp className={`w-3.5 h-3.5 ${rating === "positive" ? selectedFeedbackIconClass : ""}`} />
                  </button>
                </Tooltip>
                <Tooltip content={t('chat.poor_response')} side="top" delay={150}>
                  <button
                    className={`p-1.5 rounded-full transition-all duration-200 group/thumb ${ rating === "negative" ? selectedFeedbackClass : idleFeedbackClass }`}
                    aria-label={t('chat.poor_response')}
                    onClick={() => handleRating("negative")}
                  >
                    <ThumbsDown className={`w-3.5 h-3.5 ${rating === "negative" ? selectedFeedbackIconClass : ""}`} />
                  </button>
                </Tooltip>
                {/* The failure block owns the retry control; the footer only
                    offers it for messages without that block. */}
                {retryAction &&
                  !message.assistantRecoveryCode &&
                  message.kind !== "backtest_job" && (
                  <Tooltip content={actionLabel(retryAction)} side="top" delay={150}>
                    <button
                      type="button"
                      className={`${retryIconButtonClass} p-1.5`}
                      aria-label={actionLabel(retryAction)}
                      onClick={() => onAction?.(retryAction)}
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                  </Tooltip>
                )}
                <Tooltip content={t('chat.more_actions')} side="top" delay={150}>
                  <button
                    onClick={toggleOptions}
                    className="p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/10 text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white transition-colors"
                    aria-label={t('chat.more_actions')}
                    aria-haspopup="menu"
                    aria-expanded={showOptions}
                  >
                    <MoreHorizontal className="w-3.5 h-3.5" />
                  </button>
                </Tooltip>

                {/* Popover Menu */}
                {showOptions && (
                  <div
                    className={`absolute ${menuPosition === "bottom" ? "top-full mt-2" : "bottom-full mb-2"} right-0 w-[220px] bg-white dark:bg-[#1f2225] rounded-[24px] border border-black/5 dark:border-white/5 py-2 z-50 animate-in fade-in zoom-in-95 duration-200`}
                    role="menu"
                  >
                    <button
                      className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                      role="menuitem"
                      onClick={() => { void handleCopy(); setShowOptions(false); }}
                    >
                      <Copy className="w-4 h-4 text-black/60 dark:text-white/60" />
                      {t('chat.copy_plaintext')}
                    </button>
                    <button
                      className="w-full flex items-center gap-4 px-5 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors text-left text-black dark:text-white text-[15px] font-medium"
                      role="menuitem"
                      onClick={() => { setShowOptions(false); onFeedback?.("bug", feedbackContext()); }}
                    >
                      <MessageSquareWarning className="w-4 h-4 text-black/60 dark:text-white/60" />
                      {t('chat.report_issue')}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function UserTurnRecovery({
  recoveryText,
  retryAction,
  retryLabel,
  onAction,
}: {
  recoveryText: string;
  retryAction?: ChatActionOption;
  retryLabel: string;
  onAction?: (action: ChatActionOption) => void;
}) {
  if (!recoveryText && !retryAction) {
    return null;
  }
  return (
    <div className="mt-2 flex max-w-[85%] flex-wrap items-center justify-end gap-2">
      {recoveryText ? (
        <p
          data-testid="user-turn-recovery"
          className="text-right text-[13px] leading-[1.45] text-black/55 dark:text-white/55"
        >
          {recoveryText}
        </p>
      ) : null}
      {retryAction ? (
        <Tooltip content={retryLabel} side="top" delay={150}>
          <button
            type="button"
            data-testid="user-turn-retry"
            aria-label={retryLabel}
            onClick={() => onAction?.(retryAction)}
            className={`${retryIconButtonClass} min-h-11 min-w-11`}
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </Tooltip>
      ) : null}
    </div>
  );
}

function ResultReadout({
  content,
  label,
}: {
  content: string;
  label: string;
}) {
  return (
    <section aria-label={label}>
      <div className="argus-result-section-label">{label}</div>
      <div className="argus-result-readout prose dark:prose-invert max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    </section>
  );
}

function ResultBreakdown({
  ariaLabel,
  content,
  label,
}: {
  ariaLabel: string;
  content: string;
  label: string;
}) {
  return (
    <section aria-label={ariaLabel}>
      <div className="argus-result-section-label">{label}</div>
      <div className="argus-result-breakdown prose dark:prose-invert max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    </section>
  );
}

function UserMessageContent({ content, mentions }: { content: string; mentions: ChatMention[] }) {
  if (mentions.length === 0) return <>{content}</>;
  const pieces = messageMentionPieces(content, mentions);

  return (
    <>
      {pieces.map((piece, index) =>
        piece.kind === "text" ? (
          <span key={`text-${index}`}>{piece.text}</span>
        ) : (
          <EntityToken
            key={`${piece.mention.id}-${index}`}
            kind={piece.mention.type}
            surface="transcript"
            title={piece.mention.description ?? piece.mention.label}
          >
            {piece.text}
          </EntityToken>
        ),
      )}
    </>
  );
}
