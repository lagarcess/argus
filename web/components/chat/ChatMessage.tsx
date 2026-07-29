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
import NextMoveRow, { NextMoveDetail, NextMoveSeparator, NextMoveTitle } from "./NextMoveRow";
import { nextExperimentAction } from "@/lib/chat-next-experiments";
import { type ChatActionOption, type ChatMention, Message } from "./types";
import { normalizeAssistantDisplayText } from "@/lib/chat-display-text";
import { writeClipboardText } from "@/lib/clipboard";
import { isRetryAction } from "@/lib/chat-retry-actions";
import {
  recoveryDisplayCopyText,
  recoveryDisplayText,
} from "@/lib/chat-recovery-display";
import { feedbackContextForMessage } from "@/lib/chat-message-feedback-context";
import { Tooltip } from "@/components/ui/Tooltip";
import GuestArtifactHint from "@/components/guest/GuestArtifactHint";
import { actionHasCardScopedOwnership } from "@/lib/chat-action-ownership";
import { confirmationPeriodAdjustmentText } from "@/lib/confirmation-period-adjustment";
import { confirmationBenchmarkAdjustmentText } from "@/lib/confirmation-benchmark-adjustment";


type ChatMessageProps = {
  message: Message;
  onAction?: (action: ChatActionOption) => void;
  onFeedback?: (type: "bug" | "feature" | "general" | "rating", context: Record<string, unknown>, rating?: "positive" | "negative") => void;
  onToast?: (message: string) => void;
  isLatest?: boolean;
  isStreaming?: boolean;
  conversationId?: string | null;
  nextMovesEnabled?: boolean;
  turnInFlight?: boolean;
  isGuest?: boolean;
  canSaveDecision?: boolean;
  onDecisionUnavailable?: (artifactId: string) => void;
  onDecisionSaved?: () => void;
  onRequestSearchUpgrade?: () => void;
  resumeDecisionArtifactId?: string | null;
  onDecisionResumeHandled?: () => void;
};

const retryIconButtonClass =
  "inline-flex items-center justify-center rounded-full text-black/60 transition-all duration-200 hover:bg-black/5 hover:text-black dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white";

export default function ChatMessage({
  message,
  onAction,
  onFeedback,
  onToast,
  isLatest,
  isStreaming,
  conversationId,
  nextMovesEnabled = true,
  turnInFlight = false,
  isGuest = false,
  canSaveDecision = true,
  onDecisionUnavailable,
  onDecisionSaved,
  onRequestSearchUpgrade,
  resumeDecisionArtifactId,
  onDecisionResumeHandled,
}: ChatMessageProps) {
  const { t, i18n } = useTranslation();
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
    if (!isUser) {
      const localizedRecovery = recoveryDisplayCopyText(message.recoveryDisplay, t);
      if (localizedRecovery) {
        return normalizeCopyText(localizedRecovery);
      }
    }
    if (message.copyText) {
      return normalizeCopyText(message.copyText);
    }
    if (message.kind === "strategy_result" && message.result) {
      if (message.result.copyText) {
        return normalizeCopyText(message.result.copyText);
      }
      const rows = message.result.metrics.map((metric) => `${metric.label}: ${metric.value}`);
      const symbols = message.result.symbols?.length
        ? `Symbols: ${message.result.symbols.join(", ")}`
        : null;
      const assumptions = message.result.assumptions?.length
        ? `Assumptions: ${message.result.assumptions.join(" • ")}`
        : null;
      return normalizeCopyText([
        message.result.strategyName,
        symbols,
        `Period: ${message.result.period}`,
        rows.join("\n"),
        message.result.benchmarkNote,
        assumptions,
        message.content ? `Assistant explanation:\n${normalizeAssistantDisplayText(message.content)}` : null,
      ].filter(Boolean).join("\n"));
    }
    if (message.kind === "strategy_confirmation" && message.confirmation) {
      if (message.confirmation.copyText) {
        return normalizeCopyText(message.confirmation.copyText);
      }
      const rows = message.confirmation.rows.map((row) => `${row.label}: ${row.value}`);
      const assumptions = message.confirmation.assumptions?.length
        ? `Assumptions: ${message.confirmation.assumptions.join(" • ")}`
        : null;
      return normalizeCopyText([
        message.confirmation.title,
        message.confirmation.summary,
        rows.join("\n"),
        assumptions,
      ].filter(Boolean).join("\n"));
    }
    return normalizeCopyText(message.content ?? "");
  };

  const handleCopy = async (text = getCopyText()) => {
    const copied = await writeClipboardText(text);
    onToast?.(t(copied ? "chat.copy_success" : "chat.copy_failed"));
  };

  const getDisplayContent = () => {
    const content = message.content ?? "";
    if (!isUser && message.recoveryDisplay) {
      const recovered = recoveryDisplayText(message.recoveryDisplay, t);
      if (recovered.trim()) {
        return recovered;
      }
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
      ? recoveryDisplayText(message.recoveryDisplay, t).trim()
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

  if (isUser && message.kind === "action") {
    return (
      <div className="flex w-full flex-col items-end animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="max-w-[85%] rounded-full border border-black/10 bg-black/[0.03] px-4 py-2.5 text-[14px] font-medium leading-[1.45] text-black/75 dark:border-white/12 dark:bg-white/[0.06] dark:text-white/75">
          {displayContent || (message.selectedAction ? actionLabel(message.selectedAction) : "")}
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
              <StrategyConfirmationCard confirmation={message.confirmation} onAction={onAction} />
              {isGuest ? <GuestArtifactHint kind="confirmation" /> : null}
            </div>
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
              className="flex w-full max-w-[min(100%,660px)] items-start gap-3 rounded-[14px] border border-amber-700/25 bg-amber-500/[0.06] px-4 py-3 dark:border-amber-300/20 dark:bg-amber-300/[0.06]"
            >
              <MessageSquareWarning
                className="mt-0.5 h-4 w-4 shrink-0 text-amber-800/70 dark:text-amber-300/70"
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1 text-[15px] leading-[1.55] tracking-[0.2px] text-black/75 dark:text-white/75">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {displayContent}
                </ReactMarkdown>
              </div>
              {retryAction ? (
                <button
                  type="button"
                  onClick={() => onAction?.(retryAction)}
                  className="shrink-0 self-center rounded-full border border-amber-700/30 px-3 py-1.5 text-[13px] font-medium text-amber-900/80 transition-colors hover:bg-amber-500/10 dark:border-amber-300/30 dark:text-amber-200/90 dark:hover:bg-amber-300/10"
                >
                  {actionLabel(retryAction)}
                </button>
              ) : null}
            </div>
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

          {!isUser && !isStreaming && message.discovery && (
            <div className="mt-3 flex w-full max-w-[min(100%,660px)] flex-col gap-2">
              <div className="flex flex-col divide-y divide-black/8 dark:divide-white/8">
                {message.discovery.candidates.map((candidate) => {
                  const sendText = t("chat.discovery_results.test_candidate", {
                    symbol: candidate.symbol,
                    defaultValue: "Backtest {{symbol}}",
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
                      <NextMoveTitle>{sendText}</NextMoveTitle>
                      {hasName ? (
                        <>
                          <NextMoveSeparator>·</NextMoveSeparator>
                          <NextMoveDetail>{candidate.name}</NextMoveDetail>
                        </>
                      ) : null}
                      {candidate.reason_text ? (
                        <>
                          <NextMoveSeparator>—</NextMoveSeparator>
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
                    // Restate the relationship: peer/comparison query_summary
                    // is bare symbols, and "search for: AAPL" reads as a test.
                    const searchSendText = t(
                      `chat.discovery_results.search_current_send_${message.discovery.relationship}`,
                      {
                        query: message.discovery.query_summary,
                        defaultValue:
                          "Search current sources for: {{query}}",
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

          {/* The result's own Try next rows are the sanctioned next-move
              surface; only mid-turn composition suppresses them. */}
          {shouldShowAssistantFooter &&
            Boolean(isLatest) &&
            !turnInFlight &&
            message.kind === "strategy_result" &&
            (message.nextExperiments?.length ?? 0) > 0 && (
              <section
                aria-label={t("chat.next_experiments.section", "Try next")}
                className="mt-2 flex w-full max-w-[min(100%,660px)] flex-col"
              >
                <div className="argus-result-section-label">
                  {t("chat.next_experiments.section", "Try next")}
                </div>
                <div className="flex w-full flex-col divide-y divide-black/8 dark:divide-white/8">
                  {(message.nextExperiments ?? []).map((row, rowIndex) => {
                    const rowLabel = t(row.labelKey, row.label);
                    // One result-level reason; captioning every row repeats it.
                    const whyText =
                      row.why && rowIndex === 0
                        ? t(`chat.next_experiments.why.${row.why.code}`, {
                            defaultValue: "",
                            ...row.why.params,
                          })
                        : "";
                    return (
                      <NextMoveRow
                        key={row.kind}
                        ariaLabel={rowLabel}
                        disabled={turnInFlight}
                        onClick={() => onAction?.(nextExperimentAction(row, rowLabel))}
                      >
                        <NextMoveTitle>{rowLabel}</NextMoveTitle>
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
                {retryAction && (
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

  const pieces: Array<string | ChatMention> = [];
  let cursor = 0;
  const remainingMentions = [...mentions];

  while (cursor < content.length) {
    let nextMatch:
      | {
          index: number;
          mention: ChatMention;
          text: string;
          mentionIndex: number;
        }
      | null = null;

    for (let mentionIndex = 0; mentionIndex < remainingMentions.length; mentionIndex++) {
      const mention = remainingMentions[mentionIndex];
      const candidates = [mention.insert_text, mention.symbol ?? "", mention.label]
        .filter(Boolean)
        .sort((a, b) => b.length - a.length);
      for (const candidate of candidates) {
        const index = content.indexOf(candidate, cursor);
        if (index < 0) continue;
        if (nextMatch === null || index < nextMatch.index) {
          nextMatch = { index, mention, text: candidate, mentionIndex };
        }
      }
    }

    if (nextMatch === null) {
      pieces.push(content.slice(cursor));
      break;
    }

    if (nextMatch.index > cursor) {
      pieces.push(content.slice(cursor, nextMatch.index));
    }
    pieces.push(nextMatch.mention);
    cursor = nextMatch.index + nextMatch.text.length;
    remainingMentions.splice(nextMatch.mentionIndex, 1);
  }

  return (
    <>
      {pieces.map((piece, index) =>
        typeof piece === "string" ? (
          <span key={`text-${index}`}>{piece}</span>
        ) : (
          <MentionText key={`${piece.id}-${index}`} mention={piece} />
        ),
      )}
    </>
  );
}

function MentionText({ mention }: { mention: ChatMention }) {
  const label = mention.type === "asset" ? mention.insert_text : mention.label;
  const color =
    mention.type === "asset"
      ? "text-[#c2a44d]"
      : "text-[#494fdf] dark:text-[#8f93ff]";

  return (
    <span
      className={`mx-0.5 inline-flex select-none items-baseline rounded-sm px-0.5 font-semibold ${color}`}
      title={mention.description ?? mention.label}
    >
      {label}
    </span>
  );
}
