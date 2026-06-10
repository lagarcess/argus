import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, AtSign } from "lucide-react";
import { useTranslation } from "react-i18next";
import { searchDiscovery, type DiscoveryItem } from "@/lib/argus-api";
import {
  discoveryPanelDisplay,
  type DiscoverySearchStatus,
} from "@/lib/chat-discovery-panel";
import { Tooltip } from "@/components/ui/Tooltip";
import { chatExploratorySuggestionsEnabled } from "@/lib/private-alpha-flags";
import {
  composerMentions,
  deleteTokenBeforeOffset,
  findMentionAtOffset,
  isComposerEmpty,
  rangeForButtonDiscoveryQuery,
  rawComposerText,
  rangeForDiscoveryItem,
  replaceRangeWithToken,
  segmentLength,
  serializeComposerSegments,
  type ComposerSegment,
} from "./composer-model";
import type { ChatMention } from "./types";

type ChatInputProps = {
  onSend: (text: string, mentions?: ChatMention[]) => void;
  disabled?: boolean;
  placeholder?: string;
};

export type DiscoverySection = {
  label: string;
  items: DiscoveryItem[];
};

export const DISCOVERY_SEARCH_LIMIT = 20;

const EMPTY_CHAT_PROMPTS: string[] = [];

export default function ChatInput({
  onSend,
  disabled = false,
  placeholder,
}: ChatInputProps) {
  const { t } = useTranslation();
  const [segments, setSegments] = useState<ComposerSegment[]>([{ type: "text", text: "" }]);
  const [composerHasContent, setComposerHasContent] = useState(false);
  const [composerRawText, setComposerRawText] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [typedText, setTypedText] = useState("");
  const [discoveryQuery, setDiscoveryQuery] = useState("");
  const [discoveryItems, setDiscoveryItems] = useState<DiscoveryItem[]>([]);
  const [discoveryStatus, setDiscoveryStatus] =
    useState<DiscoverySearchStatus>("idle");
  const [isDiscoveryOpen, setIsDiscoveryOpen] = useState(false);
  const [activeDiscoveryItemId, setActiveDiscoveryItemId] = useState<string | null>(null);
  const [animState, setAnimState] = useState<"idle" | "typing" | "waiting" | "exiting">("idle");
  const [currentPromptIndex, setCurrentPromptIndex] = useState(0);
  const [isMounted, setIsMounted] = useState(false);
  const activityTimerRef = useRef<NodeJS.Timeout | null>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const pendingCaretOffsetRef = useRef<number | null>(null);
  const activeMentionOffsetRef = useRef<number | null>(null);
  const buttonDiscoveryAnchorOffsetRef = useRef<number | null>(null);
  const buttonDiscoveryQueryEndOffsetRef = useRef<number | null>(null);
  const composerIsEmpty = !composerHasContent;

  const localizedPrompts = useMemo(() => {
    const p = t("chat.placeholder_prompts", { returnObjects: true });
    return Array.isArray(p) ? p : [];
  }, [t]);
  const prompts = chatExploratorySuggestionsEnabled ? localizedPrompts : EMPTY_CHAT_PROMPTS;
  const inputPlaceholder = placeholder ?? t("chat.input_placeholder");
  const discoverySections = useMemo(
    () => discoverySectionsForDisplay(discoveryItems, discoveryQuery),
    [discoveryItems, discoveryQuery],
  );
  const visibleDiscoveryItems = useMemo(
    () => discoverySections.flatMap((section) => section.items),
    [discoverySections],
  );
  const discoveryPanel = discoveryPanelDisplay({
    itemCount: visibleDiscoveryItems.length,
    query: discoveryQuery,
    status: discoveryStatus,
  });
  const activeDiscoveryItem =
    visibleDiscoveryItems.find((item) => item.id === activeDiscoveryItemId) ?? null;
  const activeDiscoveryOptionId = activeDiscoveryItem
    ? discoveryOptionDomId(activeDiscoveryItem.id)
    : undefined;
  const sendButtonDisabled = composerIsEmpty || disabled;
  const sendDisabledReason = composerIsEmpty
    ? t("chat.message_empty", "Message is empty")
    : undefined;
  const sendButtonLabel = t("chat.send_message", "Send message");
  const isMentionButtonHidden = shouldHideMentionButton(isDiscoveryOpen, composerRawText);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!isMounted) return;

    if (!composerIsEmpty || isFocused) {
      setAnimState("idle");
      setTypedText("");
      if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
      return;
    }

    const startCycle = () => {
      if (prompts.length === 0) return;
      setCurrentPromptIndex((prev) => (prev + 1) % prompts.length);
      setAnimState("typing");
    };

    if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
    activityTimerRef.current = setTimeout(startCycle, 2000);

    return () => {
      if (activityTimerRef.current) clearTimeout(activityTimerRef.current);
    };
  }, [composerIsEmpty, isFocused, prompts.length, isMounted]);

  useEffect(() => {
    if (!isMounted || animState === "idle") return;

    if (animState === "typing") {
      const prompt = prompts[currentPromptIndex];
      if (!prompt) return;

      let i = 0;
      const interval = setInterval(() => {
        setTypedText(prompt.slice(0, i + 1));
        i++;
        if (i >= prompt.length) {
          clearInterval(interval);
          setAnimState("waiting");
        }
      }, 40);
      return () => clearInterval(interval);
    }

    if (animState === "waiting") {
      const timer = setTimeout(() => setAnimState("exiting"), 3000);
      return () => clearTimeout(timer);
    }

    if (animState === "exiting") {
      const timer = setTimeout(() => {
        setTypedText("");
        setCurrentPromptIndex((prev) => (prev + 1) % prompts.length);
        setAnimState("typing");
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [animState, currentPromptIndex, prompts, isMounted]);

  useEffect(() => {
    if (!isDiscoveryOpen) return;
    const query = discoveryQuery.trim();
    if (!query) {
      setDiscoveryItems([]);
      setDiscoveryStatus("idle");
      return;
    }

    let cancelled = false;
    setDiscoveryItems([]);
    setDiscoveryStatus("loading");
    const timer = setTimeout(() => {
      Promise.allSettled([
        searchDiscovery("assets", query, DISCOVERY_SEARCH_LIMIT),
        searchDiscovery("indicators", query, DISCOVERY_SEARCH_LIMIT),
      ]).then(([assetsResult, indicatorsResult]) => {
        if (cancelled) return;
        const assets =
          assetsResult.status === "fulfilled" ? assetsResult.value?.items ?? [] : [];
        const indicators =
          indicatorsResult.status === "fulfilled"
            ? indicatorsResult.value?.items ?? []
            : [];
        const merged = mergeDiscoveryItems(
          assets,
          indicators,
          query,
          DISCOVERY_SEARCH_LIMIT,
        );
        const didSearchFail =
          assetsResult.status === "rejected" ||
          indicatorsResult.status === "rejected";

        setDiscoveryItems(merged);
        setDiscoveryStatus(
          merged.length > 0 ? "ready" : didSearchFail ? "error" : "empty",
        );
      });
    }, 180);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [discoveryQuery, isDiscoveryOpen]);

  useEffect(() => {
    if (!isDiscoveryOpen) {
      setActiveDiscoveryItemId(null);
      return;
    }

    setActiveDiscoveryItemId((current) => {
      if (current && visibleDiscoveryItems.some((item) => item.id === current)) {
        return current;
      }
      return visibleDiscoveryItems[0]?.id ?? null;
    });
  }, [isDiscoveryOpen, visibleDiscoveryItems]);

  useEffect(() => {
    if (!isDiscoveryOpen || !activeDiscoveryItemId) return;
    document
      .getElementById(discoveryOptionDomId(activeDiscoveryItemId))
      ?.scrollIntoView({ block: "nearest" });
  }, [activeDiscoveryItemId, isDiscoveryOpen]);

  useLayoutEffect(() => {
    writeSegmentsToEditor(editorRef.current, segments);
    setComposerHasContent(!isComposerEmpty(segments));
    setComposerRawText(rawComposerText(segments));
    if (pendingCaretOffsetRef.current === null) return;
    const offset = pendingCaretOffsetRef.current;
    pendingCaretOffsetRef.current = null;
    setCaretTextOffset(editorRef.current, offset);
  }, [segments]);

  const readCurrentSegments = () => {
    const current = readSegmentsFromEditor(editorRef.current);
    return current.length > 0 ? current : segments;
  };

  const updateDiscoveryState = (current: ComposerSegment[], cursor: number | null) => {
    const rawText = rawComposerText(current);
    const currentCursor = cursor ?? rawText.length;
    const mention = findMentionAtOffset(current, currentCursor);

    if (mention) {
      buttonDiscoveryAnchorOffsetRef.current = null;
      buttonDiscoveryQueryEndOffsetRef.current = null;
      activeMentionOffsetRef.current = currentCursor;
      setIsDiscoveryOpen(true);
      setDiscoveryQuery(mention.query);
      if (!mention.query.trim()) {
        setDiscoveryItems([]);
        setDiscoveryStatus("idle");
      }
      return;
    }

    if (buttonDiscoveryAnchorOffsetRef.current !== null) {
      const anchor = buttonDiscoveryAnchorOffsetRef.current;
      const range = rangeForButtonDiscoveryQuery(rawText, anchor, currentCursor);
      if (!range) {
        closeDiscovery();
        return;
      }
      buttonDiscoveryQueryEndOffsetRef.current = range.end;
      setIsDiscoveryOpen(true);
      setDiscoveryQuery(range.query);
      if (!range.query.trim()) {
        setDiscoveryItems([]);
        setDiscoveryStatus("idle");
      }
      return;
    }

    if (isDiscoveryOpen && !rawComposerText(current).includes("@")) {
      activeMentionOffsetRef.current = null;
      setIsDiscoveryOpen(false);
      setDiscoveryItems([]);
      setDiscoveryStatus("idle");
      setActiveDiscoveryItemId(null);
    }
  };

  const closeDiscovery = () => {
    activeMentionOffsetRef.current = null;
    buttonDiscoveryAnchorOffsetRef.current = null;
    buttonDiscoveryQueryEndOffsetRef.current = null;
    setIsDiscoveryOpen(false);
    setDiscoveryItems([]);
    setDiscoveryStatus("idle");
    setActiveDiscoveryItemId(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (disabled) return;
    const current = readCurrentSegments();
    const message = serializeComposerSegments(current);
    if (message) {
      onSend(message, composerMentions(current));
      setSegments([{ type: "text", text: "" }]);
      setComposerHasContent(false);
      setComposerRawText("");
      closeDiscovery();
    }
  };

  const handleContainerClick = () => {
    editorRef.current?.focus();
  };

  const openDiscovery = () => {
    editorRef.current?.focus();
    const current = readCurrentSegments();
    const cursor = getCaretTextOffset(editorRef.current) ?? rawComposerText(current).length;
    const mention = findMentionAtOffset(current, cursor);

    if (!mention && buttonDiscoveryAnchorOffsetRef.current !== null && isDiscoveryOpen) {
      closeDiscovery();
      return;
    }

    if (!mention) {
      activeMentionOffsetRef.current = null;
      buttonDiscoveryAnchorOffsetRef.current = cursor;
      buttonDiscoveryQueryEndOffsetRef.current = cursor;
      setDiscoveryItems([]);
      setDiscoveryStatus("idle");
    } else {
      buttonDiscoveryAnchorOffsetRef.current = null;
      buttonDiscoveryQueryEndOffsetRef.current = null;
      activeMentionOffsetRef.current = cursor;
      if (!mention.query.trim()) {
        setDiscoveryItems([]);
        setDiscoveryStatus("idle");
      }
    }

    setIsDiscoveryOpen(true);
    setDiscoveryQuery(mention?.query ?? "");
  };

  const insertDiscoveryItem = (item: DiscoveryItem) => {
    const current = readCurrentSegments();
    const rawText = rawComposerText(current);
    const cursor =
      activeMentionOffsetRef.current ??
      getCaretTextOffset(editorRef.current) ??
      rawText.length;
    const buttonAnchor = buttonDiscoveryAnchorOffsetRef.current;
    const mention =
      buttonAnchor !== null
        ? rangeForButtonDiscoveryQuery(
            rawText,
            buttonAnchor,
            buttonDiscoveryQueryEndOffsetRef.current ?? cursor,
          ) ?? { start: buttonAnchor, end: buttonAnchor, query: "" }
        : rangeForDiscoveryItem(current, cursor, item) ?? { start: cursor, end: cursor, query: "" };
    const next = replaceRangeWithToken(current, mention, item);
    const tokenEnd = mention.start + item.insert_text.length;
    pendingCaretOffsetRef.current =
      rawText.slice(mention.end).trim().length > 0
        ? rawComposerText(next).length
        : rawComposerText(next)[tokenEnd] === " "
          ? tokenEnd + 1
          : tokenEnd;
    setSegments(next);
    setComposerRawText(rawComposerText(next));
    activeMentionOffsetRef.current = null;
    buttonDiscoveryAnchorOffsetRef.current = null;
    buttonDiscoveryQueryEndOffsetRef.current = null;
    setIsDiscoveryOpen(false);
    setDiscoveryItems([]);
    setDiscoveryStatus("idle");
    setActiveDiscoveryItemId(null);
  };

  const handleEditorInput = () => {
    const current = readCurrentSegments();
    const cursor = getCaretTextOffset(editorRef.current);
    setComposerHasContent(!isComposerEmpty(current));
    setComposerRawText(rawComposerText(current));
    updateDiscoveryState(current, cursor);
  };

  return (
    <form
      onSubmit={handleSubmit}
      onClick={handleContainerClick}
      className="group relative flex min-h-[64px] w-full cursor-text items-center rounded-[32px] border border-black/5 bg-white transition-all focus-within:ring-2 focus-within:ring-black/20 dark:border-white/5 dark:bg-[#1f2227] dark:focus-within:ring-white/20"
    >
      {isDiscoveryOpen && (
        <div
          id="chat-discovery-listbox"
          role="listbox"
          aria-label={t("chat.discovery.prompt", "Mention an asset or indicator")}
          aria-busy={discoveryPanel.busy}
          className="absolute bottom-full left-0 z-30 mb-2 w-full overflow-hidden rounded-[20px] border border-black/10 bg-white dark:border-white/10 dark:bg-[#1f2227]"
        >
          <div className="border-b border-black/5 px-4 py-2 text-[12px] font-medium text-black/45 dark:border-white/5 dark:text-white/45">
            {t(discoveryPanel.headerKey, discoveryPanel.headerFallback)}
          </div>
          {discoverySections.length > 0 ? (
            <div className="max-h-64 overflow-y-auto py-1">
              {discoverySections.map((section) => (
                <div key={section.label}>
                  <div className="px-4 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-black/35 dark:text-white/35">
                    {t(discoverySectionLabelKey(section.label), section.label)}
                  </div>
                  {section.items.map((item) => (
                    <button
                      key={item.id}
                      id={discoveryOptionDomId(item.id)}
                      type="button"
                      role="option"
                      aria-selected={item.id === activeDiscoveryItemId}
                      data-active-discovery-option={item.id === activeDiscoveryItemId ? "true" : undefined}
                      onMouseEnter={() => setActiveDiscoveryItemId(item.id)}
                      onClick={() => insertDiscoveryItem(item)}
                      className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors ${
                        item.id === activeDiscoveryItemId
                          ? "bg-black/5 dark:bg-white/5"
                          : "hover:bg-black/5 dark:hover:bg-white/5"
                      }`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-[14px] font-medium text-black dark:text-white">
                          {item.label}
                        </span>
                        <span className="block truncate text-[12px] text-black/45 dark:text-white/45">
                          {discoveryDescriptionLabel(item, t)}
                        </span>
                      </span>
                      <span className="shrink-0 rounded-full bg-black/[0.04] px-2 py-1 text-[11px] text-black/50 dark:bg-white/[0.06] dark:text-white/50">
                        {t(`chat.discovery.badges.${discoveryBadgeLabel(item)}`, discoveryBadgeLabel(item))}
                      </span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          ) : discoveryPanel.showBody ? (
            <div className="px-4 py-4 text-[14px] text-black/50 dark:text-white/50">
              {t(
                discoveryPanel.bodyKey,
                {
                  ...(discoveryPanel.bodyValues ?? {}),
                  defaultValue: discoveryPanel.bodyFallback,
                },
              )}
            </div>
          ) : null}
        </div>
      )}

      <button
        type="button"
        onMouseDown={(event) => event.preventDefault()}
        onClick={(event) => {
          event.stopPropagation();
          openDiscovery();
        }}
        className={`absolute left-3 top-1/2 z-20 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full text-black/45 transition-colors hover:bg-black/5 hover:text-black dark:text-white/45 dark:hover:bg-white/5 dark:hover:text-white ${
          isMentionButtonHidden ? "invisible pointer-events-none" : ""
        }`}
        aria-hidden={isMentionButtonHidden}
        tabIndex={isMentionButtonHidden ? -1 : 0}
        aria-label={t("chat.discovery.prompt", "Mention an asset or indicator")}
        aria-haspopup="listbox"
        aria-expanded={isMentionButtonHidden ? undefined : isDiscoveryOpen}
        aria-controls={!isMentionButtonHidden && isDiscoveryOpen ? "chat-discovery-listbox" : undefined}
      >
        <AtSign className="h-4 w-4" />
      </button>

      <div className="relative flex min-w-0 flex-1 flex-col justify-center py-2 pl-14 pr-2">
        <div
          ref={editorRef}
          data-testid="chat-input"
          role="combobox"
          aria-disabled={disabled}
          aria-label={inputPlaceholder}
          aria-haspopup="listbox"
          aria-autocomplete="list"
          aria-expanded={isDiscoveryOpen}
          aria-controls={isDiscoveryOpen ? "chat-discovery-listbox" : undefined}
          aria-activedescendant={isDiscoveryOpen ? activeDiscoveryOptionId : undefined}
          contentEditable={!disabled}
          suppressContentEditableWarning
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onInput={handleEditorInput}
          onPaste={(e) => {
            e.preventDefault();
            document.execCommand("insertText", false, e.clipboardData.getData("text/plain"));
          }}
          onKeyDown={(e) => {
            if (isDiscoveryOpen) {
              if (e.key === "Escape") {
                e.preventDefault();
                closeDiscovery();
                return;
              }
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActiveDiscoveryItemId((current) =>
                  nextDiscoveryItemId(visibleDiscoveryItems, current, 1),
                );
                return;
              }
              if (e.key === "ArrowUp") {
                e.preventDefault();
                setActiveDiscoveryItemId((current) =>
                  nextDiscoveryItemId(visibleDiscoveryItems, current, -1),
                );
                return;
              }
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                const action = discoveryEnterAction({
                  hasActiveItem: Boolean(activeDiscoveryItem),
                  hasComposerContent: composerHasContent,
                });
                if (action === "insert" && activeDiscoveryItem) {
                  insertDiscoveryItem(activeDiscoveryItem);
                } else if (action === "submit") {
                  closeDiscovery();
                  editorRef.current?.closest("form")?.requestSubmit();
                } else {
                  closeDiscovery();
                }
                return;
              }
            }
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              editorRef.current?.closest("form")?.requestSubmit();
            } else if (e.key === "Backspace") {
              const current = readCurrentSegments();
              const cursor = getCaretTextOffset(editorRef.current);
              if (cursor !== null && window.getSelection()?.isCollapsed) {
                const next = deleteTokenBeforeOffset(current, cursor);
                if (next.segments !== current) {
                  e.preventDefault();
                  pendingCaretOffsetRef.current = next.offset;
                  setSegments(next.segments);
                  updateDiscoveryState(next.segments, next.offset);
                }
              }
            } else if (e.key === "@" && !e.ctrlKey && !e.metaKey && !e.altKey) {
              buttonDiscoveryAnchorOffsetRef.current = null;
              buttonDiscoveryQueryEndOffsetRef.current = null;
              activeMentionOffsetRef.current = null;
              setIsDiscoveryOpen(true);
              setDiscoveryQuery("");
              setDiscoveryItems([]);
              setDiscoveryStatus("idle");
            }
          }}
          className="min-h-[1.45em] flex-1 whitespace-pre-wrap break-words border-none bg-transparent p-0 text-[16px] font-medium leading-[1.45] tracking-tight text-black outline-none dark:text-white"
        />

        {isMounted && animState === "idle" && composerIsEmpty && !isFocused && (
          <div className="pointer-events-none absolute inset-y-0 left-14 flex items-center text-[16px] font-medium leading-[1.45] tracking-tight text-gray-400 transition-opacity group-focus-within:invisible group-focus-within:opacity-0 dark:text-gray-500">
            {inputPlaceholder}
          </div>
        )}

        {isMounted && animState !== "idle" && composerIsEmpty && (
          <div
            key={`${currentPromptIndex}-${animState === "exiting"}`}
            className={`pointer-events-none absolute inset-y-0 left-14 flex max-w-[calc(100%-4rem)] items-center overflow-hidden whitespace-nowrap text-[16px] font-medium leading-[1.45] tracking-tight text-gray-400 transition-opacity group-focus-within:invisible group-focus-within:opacity-0 dark:text-gray-500 ${animState === "exiting" ? "animate-argus-swoosh-up" : ""}`}
          >
            {typedText}
            {animState === "typing" && (
              <span className="ml-0.5 h-4 w-[2px] animate-pulse bg-black/30 dark:bg-white/30" />
            )}
          </div>
        )}
      </div>

      <div className="flex h-14 w-14 shrink-0 self-center items-center justify-center">
        {sendDisabledReason ? (
          <Tooltip content={sendDisabledReason} side="top" delay={150}>
            <span
              data-testid="chat-send-disabled-tooltip"
              aria-disabled="true"
              aria-label={sendDisabledReason}
              tabIndex={0}
              onClick={(event) => event.stopPropagation()}
              className="inline-flex h-11 w-11 rounded-full"
            >
              <SendButton disabled={sendButtonDisabled} ariaLabel={sendButtonLabel} />
            </span>
          </Tooltip>
        ) : (
          <SendButton disabled={sendButtonDisabled} ariaLabel={sendButtonLabel} />
        )}
      </div>
    </form>
  );
}

function SendButton({ disabled, ariaLabel }: { disabled: boolean; ariaLabel: string }) {
  return (
    <button
      type="submit"
      data-testid="chat-send"
      disabled={disabled}
      aria-label={ariaLabel}
      className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-black text-white transition-opacity hover:opacity-85 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-black"
    >
      <ArrowUp className="h-5 w-5 stroke-[2.5]" />
    </button>
  );
}

function rankDiscoveryItem(item: DiscoveryItem, query: string) {
  const normalized = query.trim().toLowerCase();
  const symbol = (item.symbol ?? "").toLowerCase();
  const label = item.label.toLowerCase();
  const exact = symbol === normalized || label === normalized;
  const prefix = symbol.startsWith(normalized) || label.startsWith(normalized);
  if (exact && item.type === "indicator") return 0;
  if (exact) return 1;
  if (prefix && item.type === "asset") return 2;
  if (prefix) return 3;
  return item.type === "asset" ? 4 : 5;
}

export function mergeDiscoveryItems(
  assets: DiscoveryItem[],
  indicators: DiscoveryItem[],
  query: string,
  limit: number,
) {
  const sortedAssets = [...assets].sort(
    (a, b) => rankDiscoveryItem(a, query) - rankDiscoveryItem(b, query),
  );
  const sortedIndicators = indicators
    .filter((item) => isSupportedDiscoveryItem(item))
    .sort((a, b) => rankDiscoveryItem(a, query) - rankDiscoveryItem(b, query));
  const merged: DiscoveryItem[] = [];
  const seen = new Set<string>();

  const push = (item: DiscoveryItem | undefined) => {
    if (!item || seen.has(item.id) || merged.length >= limit) return;
    seen.add(item.id);
    merged.push(item);
  };

  for (
    let index = 0;
    merged.length < limit &&
    (index < sortedAssets.length || index < sortedIndicators.length);
    index++
  ) {
    const indicator = sortedIndicators[index];
    const asset = sortedAssets[index];
    if (indicator && rankDiscoveryItem(indicator, query) <= 1) {
      push(indicator);
      push(asset);
    } else {
      push(asset);
      push(indicator);
    }
  }

  return merged;
}

export function discoverySectionsForDisplay(
  items: DiscoveryItem[],
  query: string,
): DiscoverySection[] {
  const visibleItems = items.filter(
    (item) => item.id && item.label && isSupportedDiscoveryItem(item),
  );
  if (visibleItems.length === 0) return [];
  if (query.trim()) {
    return [{ label: "Search results", items: visibleItems }];
  }

  const sections: DiscoverySection[] = [
    {
      label: "Popular assets",
      items: visibleItems.filter((item) => item.type === "asset"),
    },
    {
      label: "Runnable indicators",
      items: visibleItems.filter(
        (item) => item.type === "indicator" && item.support_status === "supported",
      ),
    },
  ];
  return sections.filter((section) => section.items.length > 0);
}

export function discoveryOptionDomId(id: string) {
  const safeId = id.replace(/[^A-Za-z0-9_-]+/g, "-");
  return `chat-discovery-option-${safeId}`;
}

export function shouldHideMentionButton(_isDiscoveryOpen: boolean, rawText: string) {
  return rawText.includes("@");
}

export function discoveryEnterAction({
  hasActiveItem,
  hasComposerContent,
}: {
  hasActiveItem: boolean;
  hasComposerContent: boolean;
}): "insert" | "submit" | "close" {
  if (hasActiveItem) return "insert";
  return hasComposerContent ? "submit" : "close";
}

export function nextDiscoveryItemId(
  items: DiscoveryItem[],
  currentId: string | null,
  direction: 1 | -1,
) {
  if (items.length === 0) return null;
  const currentIndex = items.findIndex((item) => item.id === currentId);
  if (currentIndex < 0) return items[0].id;
  const nextIndex = (currentIndex + direction + items.length) % items.length;
  return items[nextIndex]?.id ?? items[0].id;
}

function discoverySectionLabelKey(label: string) {
  if (label === "Popular assets") return "chat.discovery.sections.assets";
  if (label === "Runnable indicators") return "chat.discovery.sections.indicators";
  return "chat.discovery.sections.results";
}

function discoveryBadgeLabel(item: DiscoveryItem) {
  if (item.type === "asset") return "asset";
  if (item.support_status === "supported") return "runnable";
  if (item.support_status === "unavailable") return "unavailable";
  return "draft";
}

function isSupportedDiscoveryItem(item: DiscoveryItem) {
  return item.type !== "indicator" || item.support_status === "supported";
}

function writeSegmentsToEditor(root: HTMLDivElement | null, segments: ComposerSegment[]) {
  if (!root) return;
  root.replaceChildren();
  for (const segment of segments) {
    if (segment.type === "text") {
      root.appendChild(document.createTextNode(segment.text));
      continue;
    }
    root.appendChild(createTokenElement(segment.token));
  }
}

function createTokenElement(item: DiscoveryItem) {
  const token = document.createElement("span");
  token.contentEditable = "false";
  token.dataset.composerToken = "true";
  token.dataset.tokenId = item.id;
  token.dataset.tokenType = item.type;
  token.dataset.tokenLabel = item.label;
  token.dataset.tokenSymbol = item.symbol ?? "";
  token.dataset.tokenAssetClass = item.asset_class ?? "";
  token.dataset.tokenDescription = displayDiscoveryDescription(item);
  token.dataset.tokenInsertText = item.insert_text;
  token.dataset.tokenProvider = item.provider;
  token.dataset.tokenSupportStatus = item.support_status;
  token.className = tokenClassName(item.type);

  const label = document.createElement("span");
  label.className = "truncate";
  label.textContent = item.type === "asset" ? item.insert_text : item.label;
  token.appendChild(label);
  return token;
}

function displayDiscoveryDescription(item: DiscoveryItem) {
  const description = item.description?.trim();
  if (!description) return item.type === "asset" ? "Asset" : "Indicator";
  if (description.toLowerCase() === "currency_pair") return "Currency Pair";
  return description.replaceAll("_", " ");
}

function discoveryDescriptionLabel(item: DiscoveryItem, t: any) {
  const description = displayDiscoveryDescription(item);
  if (description === "Asset") {
    return t("chat.discovery.descriptions.asset", description);
  }
  if (description === "Indicator") {
    return t("chat.discovery.descriptions.indicator", description);
  }
  if (description === "Currency Pair") {
    return t("chat.discovery.descriptions.currency_pair", description);
  }
  return description;
}

function tokenClassName(type: DiscoveryItem["type"]) {
  const base =
    "mx-0.5 inline-flex max-w-40 select-none items-center rounded-sm px-0.5 py-0 text-[1em] font-semibold leading-[1.35] align-baseline";
  const asset =
    "text-[#c2a44d]";
  const indicator =
    "text-[#494fdf] dark:text-[#8f93ff]";
  return `${base} ${type === "asset" ? asset : indicator}`;
}

function assetClassFromDataset(value: string | undefined): DiscoveryItem["asset_class"] {
  if (value === "equity" || value === "crypto" || value === "currency_pair") {
    return value;
  }
  return null;
}

function readSegmentsFromEditor(root: HTMLDivElement | null): ComposerSegment[] {
  if (!root) return [{ type: "text", text: "" }];
  const segments: ComposerSegment[] = [];

  const appendText = (text: string) => {
    if (!text) return;
    const previous = segments.at(-1);
    if (previous?.type === "text") {
      previous.text += text;
    } else {
      segments.push({ type: "text", text });
    }
  };

  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      appendText(node.textContent ?? "");
      return;
    }
    if (!(node instanceof HTMLElement)) return;
    if (node.dataset.composerToken === "true") {
      segments.push({
        type: "token",
        token: {
          id: node.dataset.tokenId ?? "",
          type: node.dataset.tokenType === "indicator" ? "indicator" : "asset",
          label: node.dataset.tokenLabel ?? node.dataset.tokenInsertText ?? "",
          symbol: node.dataset.tokenSymbol || null,
          asset_class: assetClassFromDataset(node.dataset.tokenAssetClass),
          description: node.dataset.tokenDescription || null,
          insert_text: node.dataset.tokenInsertText ?? node.textContent ?? "",
          provider: node.dataset.tokenProvider ?? "",
          support_status:
            node.dataset.tokenSupportStatus === "draft_only" ||
            node.dataset.tokenSupportStatus === "unavailable"
              ? node.dataset.tokenSupportStatus
              : "supported",
        },
      });
      return;
    }
    if (node.tagName === "BR") {
      appendText("\n");
      return;
    }
    node.childNodes.forEach(walk);
    if (node !== root && (node.tagName === "DIV" || node.tagName === "P")) {
      appendText("\n");
    }
  };

  root.childNodes.forEach(walk);
  return segments.length > 0 ? segments : [{ type: "text", text: "" }];
}

function getCaretTextOffset(root: HTMLDivElement | null) {
  if (!root) return null;
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0);
  if (!root.contains(range.startContainer)) return null;
  return countOffset(root, range.startContainer, range.startOffset);
}

function countOffset(root: Node, target: Node, targetOffset: number) {
  let offset = 0;
  let found = false;

  const walk = (node: Node) => {
    if (found) return;
    if (node === target) {
      if (node.nodeType === Node.TEXT_NODE) {
        offset += targetOffset;
      } else {
        node.childNodes.forEach((child, index) => {
          if (index < targetOffset) offset += nodeTextLength(child);
        });
      }
      found = true;
      return;
    }
    if (containsNode(node, target)) {
      node.childNodes.forEach(walk);
      return;
    }
    offset += nodeTextLength(node);
  };

  root.childNodes.forEach(walk);
  return offset;
}

function nodeTextLength(node: Node): number {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent?.length ?? 0;
  if (node instanceof HTMLElement && node.dataset.composerToken === "true") {
    return node.dataset.tokenInsertText?.length ?? node.textContent?.length ?? 0;
  }
  if (node instanceof HTMLElement && node.tagName === "BR") return 1;
  let length = 0;
  node.childNodes.forEach((child) => {
    length += nodeTextLength(child);
  });
  return length;
}

function containsNode(parent: Node, child: Node) {
  return parent === child || parent.contains(child);
}

function setCaretTextOffset(root: HTMLDivElement | null, targetOffset: number) {
  if (!root) return;
  root.focus();
  const selection = window.getSelection();
  if (!selection) return;
  const range = document.createRange();
  let cursor = 0;
  let placed = false;

  const walk = (node: Node) => {
    if (placed) return;
    if (node.nodeType === Node.TEXT_NODE) {
      const length = node.textContent?.length ?? 0;
      if (cursor + length >= targetOffset) {
        range.setStart(node, Math.max(0, targetOffset - cursor));
        placed = true;
        return;
      }
      cursor += length;
      return;
    }
    if (node instanceof HTMLElement && node.dataset.composerToken === "true") {
      const length = segmentLength({
        type: "token",
        token: {
          id: node.dataset.tokenId ?? "",
          type: node.dataset.tokenType === "indicator" ? "indicator" : "asset",
          label: node.dataset.tokenLabel ?? "",
          symbol: node.dataset.tokenSymbol || null,
          asset_class: assetClassFromDataset(node.dataset.tokenAssetClass),
          description: node.dataset.tokenDescription || null,
          insert_text: node.dataset.tokenInsertText ?? node.textContent ?? "",
          provider: node.dataset.tokenProvider ?? "",
          support_status: "supported",
        },
      });
      if (cursor + length >= targetOffset) {
        range.setStartAfter(node);
        placed = true;
        return;
      }
      cursor += length;
      return;
    }
    node.childNodes.forEach(walk);
  };

  root.childNodes.forEach(walk);
  if (!placed) {
    range.selectNodeContents(root);
    range.collapse(false);
  }
  selection.removeAllRanges();
  selection.addRange(range);
}
