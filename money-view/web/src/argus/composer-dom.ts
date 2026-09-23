// Adapted from web/components/chat/ChatInput.tsx DOM helpers. See REUSE.md.
import type { Mention as DiscoveryItem } from "./types";
import {
  composerTokenAtCaret,
  segmentLength,
  type ComposerSegment,
} from "./composer-model";
export function writeSegmentsToEditor(
  root: HTMLDivElement | null,
  segments: ComposerSegment[],
) {
  if (!root) return;
  root.replaceChildren();
  let offset = 0;
  for (const segment of segments) {
    if (segment.type === "text") {
      root.appendChild(document.createTextNode(segment.text));
      offset += segment.text.length;
      continue;
    }
    root.appendChild(createTokenElement(segment.token, offset));
    offset += segmentLength(segment);
  }
}

function createTokenElement(item: DiscoveryItem, start: number) {
  const token = document.createElement("span");
  token.contentEditable = "false";
  token.dataset.composerToken = "true";
  token.dataset.entityToken = "true";
  token.dataset.entityTokenFocused = "false";
  token.dataset.entityTokenKind = item.type;
  token.dataset.entityTokenSurface = "composer";
  token.dataset.tokenId = item.id;
  token.dataset.tokenStart = String(start);
  token.dataset.tokenEnd = String(start + item.insert_text.length);
  token.dataset.tokenType = item.type;
  token.dataset.tokenLabel = item.label;
  token.dataset.tokenSymbol = item.symbol ?? "";
  token.dataset.tokenAssetClass = "";
  token.dataset.tokenDescription = displayDiscoveryDescription(item);
  token.dataset.tokenInsertText = item.insert_text;
  token.dataset.tokenProvider = item.provider ?? "";
  token.className = "argus-mention-token";

  const label = document.createElement("span");
  label.className = "truncate";
  label.textContent = item.type === "asset" ? item.insert_text : item.label;
  token.appendChild(label);
  return token;
}

export function syncComposerTokenFocus(
  root: HTMLDivElement | null,
  segments: ComposerSegment[],
) {
  if (!root) return;
  const selection = window.getSelection();
  const range = selection?.rangeCount ? selection.getRangeAt(0) : null;
  const offset =
    selection?.isCollapsed && range && root.contains(range.startContainer)
      ? getCaretTextOffset(root)
      : null;
  const focused =
    offset === null ? null : composerTokenAtCaret(segments, offset);
  root
    .querySelectorAll<HTMLElement>("[data-composer-token]")
    .forEach((token) => {
      token.dataset.entityTokenFocused =
        focused &&
        token.dataset.tokenStart === String(focused.start) &&
        token.dataset.tokenEnd === String(focused.end)
          ? "true"
          : "false";
    });
}

export function clearComposerTokenFocus(root: HTMLDivElement | null) {
  root
    ?.querySelectorAll<HTMLElement>("[data-composer-token]")
    .forEach((token) => {
      token.dataset.entityTokenFocused = "false";
    });
}

function displayDiscoveryDescription(item: DiscoveryItem) {
  const description = item.description?.trim();
  if (!description) return item.label;
  if (description.toLowerCase() === "currency_pair") return "Currency Pair";
  return description.replaceAll("_", " ");
}

export function readSegmentsFromEditor(
  root: HTMLDivElement | null,
): ComposerSegment[] {
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
          type: node.dataset.tokenType ?? "record",
          label: node.dataset.tokenLabel ?? node.dataset.tokenInsertText ?? "",
          symbol: node.dataset.tokenSymbol || null,
          description: node.dataset.tokenDescription || null,
          insert_text: node.dataset.tokenInsertText ?? node.textContent ?? "",
          provider: node.dataset.tokenProvider ?? "",
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

export function getCaretTextOffset(root: HTMLDivElement | null) {
  if (!root) return null;
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0);
  if (!root.contains(range.startContainer)) return null;
  return countOffset(root, range.startContainer, range.startOffset);
}

function countOffset(root: Node, target: Node, targetOffset: number) {
  if (root === target) {
    let rootOffset = 0;
    for (let index = 0; index < targetOffset; index += 1) {
      const child = root.childNodes[index];
      if (child) rootOffset += nodeTextLength(child);
    }
    return rootOffset;
  }
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
    return (
      node.dataset.tokenInsertText?.length ?? node.textContent?.length ?? 0
    );
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

export function setCaretTextOffset(
  root: HTMLDivElement | null,
  targetOffset: number,
) {
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
          type: node.dataset.tokenType ?? "record",
          label: node.dataset.tokenLabel ?? "",
          symbol: node.dataset.tokenSymbol || null,
          description: node.dataset.tokenDescription || null,
          insert_text: node.dataset.tokenInsertText ?? node.textContent ?? "",
          provider: node.dataset.tokenProvider ?? "",
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
