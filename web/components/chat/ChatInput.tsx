import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, AtSign } from "lucide-react";
import { useTranslation } from "react-i18next";
import { searchDiscovery, type DiscoveryItem } from "@/lib/argus-api";
import {
  deleteTokenBeforeOffset,
  findMentionAtOffset,
  insertTextAtOffset,
  isComposerEmpty,
  rawComposerText,
  rangeForDiscoveryItem,
  replaceRangeWithToken,
  segmentLength,
  serializeComposerSegments,
  type ComposerSegment,
} from "./composer-model";

type ChatInputProps = {
  onSend: (text: string) => void;
};

export default function ChatInput({ onSend }: ChatInputProps) {
  const { t } = useTranslation();
  const [segments, setSegments] = useState<ComposerSegment[]>([{ type: "text", text: "" }]);
  const [composerHasContent, setComposerHasContent] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [typedText, setTypedText] = useState("");
  const [discoveryQuery, setDiscoveryQuery] = useState("");
  const [discoveryItems, setDiscoveryItems] = useState<DiscoveryItem[]>([]);
  const [isDiscoveryOpen, setIsDiscoveryOpen] = useState(false);
  const [animState, setAnimState] = useState<"idle" | "typing" | "waiting" | "exiting">("idle");
  const [currentPromptIndex, setCurrentPromptIndex] = useState(0);
  const [isMounted, setIsMounted] = useState(false);
  const activityTimerRef = useRef<NodeJS.Timeout | null>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const pendingCaretOffsetRef = useRef<number | null>(null);
  const activeMentionOffsetRef = useRef<number | null>(null);
  const composerIsEmpty = !composerHasContent;

  const prompts = useMemo(() => {
    const p = t("chat.placeholder_prompts", { returnObjects: true });
    return Array.isArray(p) ? p : [];
  }, [t]);

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
    if (!query) return;

    let cancelled = false;
    const timer = setTimeout(() => {
      Promise.all([
        searchDiscovery("assets", query, 5).catch(() => ({ items: [] })),
        searchDiscovery("indicators", query, 5).catch(() => ({ items: [] })),
      ]).then(([assets, indicators]) => {
        if (cancelled) return;
        setDiscoveryItems(
          [...assets.items, ...indicators.items]
            .sort((a, b) => rankDiscoveryItem(a, query) - rankDiscoveryItem(b, query))
            .slice(0, 8),
        );
      });
    }, 180);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [discoveryQuery, isDiscoveryOpen]);

  useLayoutEffect(() => {
    writeSegmentsToEditor(editorRef.current, segments);
    setComposerHasContent(!isComposerEmpty(segments));
    if (pendingCaretOffsetRef.current === null) return;
    const offset = pendingCaretOffsetRef.current;
    pendingCaretOffsetRef.current = null;
    requestAnimationFrame(() => setCaretTextOffset(editorRef.current, offset));
  }, [segments]);

  const readCurrentSegments = () => {
    const current = readSegmentsFromEditor(editorRef.current);
    return current.length > 0 ? current : segments;
  };

  const updateDiscoveryState = (current: ComposerSegment[], cursor: number | null) => {
    const mention = findMentionAtOffset(current, cursor ?? rawComposerText(current).length);
    if (mention) {
      activeMentionOffsetRef.current = cursor ?? rawComposerText(current).length;
      setIsDiscoveryOpen(true);
      setDiscoveryQuery(mention.query);
      if (!mention.query.trim()) {
        setDiscoveryItems(DEFAULT_DISCOVERY_ITEMS);
      }
    } else if (isDiscoveryOpen && !rawComposerText(current).includes("@")) {
      activeMentionOffsetRef.current = null;
      setIsDiscoveryOpen(false);
      setDiscoveryItems([]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const message = serializeComposerSegments(readCurrentSegments());
    if (message) {
      onSend(message);
      setSegments([{ type: "text", text: "" }]);
      setComposerHasContent(false);
      setIsDiscoveryOpen(false);
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

    if (!mention) {
      const next = insertTextAtOffset(current, cursor, "@");
      pendingCaretOffsetRef.current = cursor + 1;
      activeMentionOffsetRef.current = cursor + 1;
      setSegments(next);
      setDiscoveryItems(DEFAULT_DISCOVERY_ITEMS);
    } else if (!mention.query.trim()) {
      activeMentionOffsetRef.current = cursor;
      setDiscoveryItems(DEFAULT_DISCOVERY_ITEMS);
    }

    setIsDiscoveryOpen(true);
    setDiscoveryQuery(mention?.query ?? "");
  };

  const insertDiscoveryItem = (item: DiscoveryItem) => {
    const current = readCurrentSegments();
    const cursor =
      activeMentionOffsetRef.current ??
      getCaretTextOffset(editorRef.current) ??
      rawComposerText(current).length;
    const mention = rangeForDiscoveryItem(current, cursor, item) ?? { start: cursor, end: cursor, query: "" };
    const currentRaw = rawComposerText(current);
    const next = replaceRangeWithToken(current, mention, item);
    const tokenEnd = mention.start + item.insert_text.length;
    pendingCaretOffsetRef.current =
      currentRaw.slice(mention.end).trim().length > 0
        ? rawComposerText(next).length
        : rawComposerText(next).at(tokenEnd) === " "
          ? tokenEnd + 1
          : tokenEnd;
    setSegments(next);
    activeMentionOffsetRef.current = null;
    setIsDiscoveryOpen(false);
    setDiscoveryItems([]);
  };

  const handleEditorInput = () => {
    const current = readCurrentSegments();
    const cursor = getCaretTextOffset(editorRef.current);
    setComposerHasContent(!isComposerEmpty(current));
    updateDiscoveryState(current, cursor);
  };

  return (
    <form
      onSubmit={handleSubmit}
      onClick={handleContainerClick}
      className="relative flex min-h-[76px] w-full cursor-text items-end rounded-[32px] border border-black/5 bg-white transition-all focus-within:ring-2 focus-within:ring-black/20 dark:border-white/5 dark:bg-[#1f2227] dark:focus-within:ring-white/20"
    >
      {isDiscoveryOpen && (
        <div className="absolute bottom-full left-0 z-30 mb-2 w-full overflow-hidden rounded-[20px] border border-black/10 bg-white dark:border-white/10 dark:bg-[#1f2227]">
          <div className="border-b border-black/5 px-4 py-2 text-[12px] font-medium text-black/45 dark:border-white/5 dark:text-white/45">
            Search assets and indicators
          </div>
          {discoveryItems.length > 0 ? (
            <div className="max-h-64 overflow-y-auto py-1">
              {discoveryItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => insertDiscoveryItem(item)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-black/5 dark:hover:bg-white/5"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-[14px] font-medium text-black dark:text-white">
                      {item.label}
                    </span>
                    <span className="block truncate text-[12px] text-black/45 dark:text-white/45">
                      {item.description}
                    </span>
                  </span>
                  <span className="shrink-0 rounded-full bg-black/[0.04] px-2 py-1 text-[11px] text-black/50 dark:bg-white/[0.06] dark:text-white/50">
                    {item.type}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="px-4 py-4 text-[14px] text-black/50 dark:text-white/50">
              Type after @ to search supported assets and indicators.
            </div>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={openDiscovery}
        className="absolute left-3 top-3 z-20 flex h-8 w-8 items-center justify-center rounded-full text-black/45 transition-colors hover:bg-black/5 hover:text-black dark:text-white/45 dark:hover:bg-white/5 dark:hover:text-white"
        aria-label="Find asset or indicator"
      >
        <AtSign className="h-4 w-4" />
      </button>

      <div className="relative flex min-w-0 flex-1 flex-col justify-center py-3 pl-14 pr-2">
        <div
          ref={editorRef}
          data-testid="chat-input"
          role="textbox"
          aria-label={t("chat.input_placeholder")}
          contentEditable
          suppressContentEditableWarning
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onInput={handleEditorInput}
          onPaste={(e) => {
            e.preventDefault();
            document.execCommand("insertText", false, e.clipboardData.getData("text/plain"));
          }}
          onKeyDown={(e) => {
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
              setIsDiscoveryOpen(true);
              setDiscoveryQuery("");
              setDiscoveryItems(DEFAULT_DISCOVERY_ITEMS);
            }
          }}
          className="min-h-[44px] flex-1 whitespace-pre-wrap break-words border-none bg-transparent p-0 text-[16px] font-medium leading-[1.45] tracking-tight text-black outline-none dark:text-white"
        />

        {isMounted && animState === "idle" && composerIsEmpty && !isFocused && (
          <div className="pointer-events-none absolute left-14 top-3 text-[16px] font-medium leading-[1.45] tracking-tight text-gray-400 dark:text-gray-500">
            {t("chat.input_placeholder")}
          </div>
        )}

        {isMounted && animState !== "idle" && composerIsEmpty && (
          <div
            key={`${currentPromptIndex}-${animState === "exiting"}`}
            className={`pointer-events-none absolute left-14 top-3 flex max-w-[calc(100%-4rem)] items-center overflow-hidden whitespace-nowrap text-[16px] font-medium leading-[1.45] tracking-tight text-gray-400 dark:text-gray-500 ${animState === "exiting" ? "animate-argus-swoosh-up" : ""}`}
          >
            {typedText}
            {animState === "typing" && (
              <span className="ml-0.5 h-4 w-[2px] animate-pulse bg-black/30 dark:bg-white/30" />
            )}
          </div>
        )}
      </div>

      <div className="shrink-0 p-2">
        <button
          type="submit"
          data-testid="chat-send"
          disabled={composerIsEmpty}
          className="rounded-full bg-black p-2.5 text-white transition-opacity hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-black"
        >
          <ArrowUp className="h-5 w-5 stroke-[2.5]" />
        </button>
      </div>
    </form>
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
  token.dataset.tokenDescription = item.description ?? "";
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

function tokenClassName(type: DiscoveryItem["type"]) {
  const base =
    "mx-0.5 inline-flex max-w-40 select-none items-center rounded-sm px-0.5 py-0 text-[1em] font-semibold leading-[1.35] align-baseline";
  const asset =
    "text-[#c2a44d]";
  const indicator =
    "text-[#494fdf] dark:text-[#8f93ff]";
  return `${base} ${type === "asset" ? asset : indicator}`;
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
  root.focus();
}

const DEFAULT_DISCOVERY_ITEMS: DiscoveryItem[] = [
  {
    id: "asset:GOOG",
    type: "asset",
    label: "GOOG",
    symbol: "GOOG",
    description: "Alphabet Class C",
    insert_text: "GOOG",
    provider: "alpaca",
    support_status: "supported",
  },
  {
    id: "asset:AAPL",
    type: "asset",
    label: "AAPL",
    symbol: "AAPL",
    description: "Apple",
    insert_text: "AAPL",
    provider: "alpaca",
    support_status: "supported",
  },
  {
    id: "asset:NVDA",
    type: "asset",
    label: "NVDA",
    symbol: "NVDA",
    description: "Nvidia",
    insert_text: "NVDA",
    provider: "alpaca",
    support_status: "supported",
  },
  {
    id: "asset:BTC",
    type: "asset",
    label: "BTC",
    symbol: "BTC",
    description: "Bitcoin",
    insert_text: "BTC",
    provider: "alpaca",
    support_status: "supported",
  },
  {
    id: "indicator:rsi",
    type: "indicator",
    label: "RSI",
    symbol: "rsi",
    description: "Relative Strength Index",
    insert_text: "RSI",
    provider: "pandas-ta-classic",
    support_status: "supported",
  },
];
