import type { DiscoveryItem } from "@/lib/argus-api";
import type { ChatMention } from "./types";

export type ComposerTextSegment = {
  type: "text";
  text: string;
};

export type ComposerTokenSegment = {
  type: "token";
  token: DiscoveryItem;
};

export type ComposerSegment = ComposerTextSegment | ComposerTokenSegment;

export type TextRange = {
  start: number;
  end: number;
  query: string;
};

export function serializeComposerSegments(segments: ComposerSegment[]) {
  return segments
    .map((segment) => (segment.type === "token" ? segment.token.insert_text : segment.text))
    .join("")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/ *\n */g, "\n")
    .trim();
}

export function composerMentions(segments: ComposerSegment[]): ChatMention[] {
  return segments
    .filter((segment): segment is ComposerTokenSegment => segment.type === "token")
    .map(({ token }) => ({
      id: token.id,
      type: token.type,
      label: token.label,
      symbol: token.symbol ?? null,
      description: token.description ?? null,
      insert_text: token.insert_text,
      support_status: token.support_status,
    }));
}

export function isComposerEmpty(segments: ComposerSegment[]) {
  return segments.every((segment) =>
    segment.type === "text" ? segment.text.trim().length === 0 : false,
  );
}

export function findMentionAtOffset(segments: ComposerSegment[], offset: number): TextRange | null {
  const text = rawComposerText(segments);
  const beforeCursor = text.slice(0, offset);
  const atIndex = beforeCursor.lastIndexOf("@");
  if (atIndex < 0) return null;

  const boundaryBefore = atIndex === 0 || /\s|\(|\[|{|,|;/.test(text.at(atIndex - 1) ?? "");
  if (!boundaryBefore) return null;

  const between = beforeCursor.slice(atIndex + 1);
  if (/[.,;!?()[\]{}]/.test(between)) return null;

  return {
    start: atIndex,
    end: offset,
    query: text.slice(atIndex + 1, offset).trimStart(),
  };
}

export function rangeForDiscoveryItem(
  segments: ComposerSegment[],
  offset: number,
  item: DiscoveryItem,
): TextRange | null {
  const mention = findMentionAtOffset(segments, offset);
  if (!mention) return null;

  const text = rawComposerText(segments);
  const queryStart = mention.start + 1;
  const suffix = text.slice(queryStart);
  const boundary = suffix.search(/[.,;!?()[\]{}]/);
  const query = (boundary < 0 ? suffix : suffix.slice(0, boundary)).trimStart();
  const normalizedQuery = normalizeSearchText(query);
  const candidates = [
    item.description,
    item.label,
    item.insert_text,
    item.symbol ?? undefined,
  ]
    .filter((candidate): candidate is string => Boolean(candidate))
    .sort((a, b) => b.length - a.length);

  for (const candidate of candidates) {
    const normalizedCandidate = normalizeSearchText(candidate);
    const nextCharacter = normalizedQuery.at(normalizedCandidate.length) ?? "";
    if (
      normalizedCandidate &&
      normalizedQuery.startsWith(normalizedCandidate) &&
      !/[a-z0-9]/.test(nextCharacter)
    ) {
      return {
        start: mention.start,
        end: mention.start + 1 + candidate.length,
        query: query.slice(0, candidate.length),
      };
    }
  }

  const firstPhrase = query.match(/^[\w-]+/u)?.[0] ?? query;
  return {
    start: mention.start,
    end: mention.start + 1 + firstPhrase.length,
    query: firstPhrase,
  };
}

export function insertTextAtOffset(
  segments: ComposerSegment[],
  offset: number,
  text: string,
): ComposerSegment[] {
  return replaceTextRange(segments, offset, offset, [{ type: "text", text }]);
}

function normalizeSearchText(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

export function replaceRangeWithToken(
  segments: ComposerSegment[],
  range: { start: number; end: number; query?: string },
  token: DiscoveryItem,
): ComposerSegment[] {
  const before = rawComposerText(segments).at(range.start - 1) ?? "";
  const after = rawComposerText(segments).at(range.end) ?? "";
  const replacement: ComposerSegment[] = [{ type: "token", token }];
  if (after && !/\s|[.,;!?)]/.test(after)) {
    replacement.push({ type: "text", text: " " });
  }
  if (!after && before && !/\s/.test(before)) {
    replacement.unshift({ type: "text", text: " " });
  }
  if (!after) {
    replacement.push({ type: "text", text: " " });
  }
  return replaceTextRange(segments, range.start, range.end, replacement);
}

export function deleteTokenBeforeOffset(segments: ComposerSegment[], offset: number) {
  let cursor = 0;
  for (let index = 0; index < segments.length; index++) {
    const segment = segments[index];
    const length = segmentLength(segment);
    const end = cursor + length;
    if (segment.type === "token" && end === offset) {
      return {
        segments: normalizeSegments([
          ...segments.slice(0, index),
          ...segments.slice(index + 1),
        ]),
        offset: cursor,
      };
    }
    cursor = end;
  }
  return { segments, offset };
}

export function rawComposerText(segments: ComposerSegment[]) {
  return segments
    .map((segment) => (segment.type === "token" ? segment.token.insert_text : segment.text))
    .join("");
}

export function segmentLength(segment: ComposerSegment) {
  return segment.type === "token" ? segment.token.insert_text.length : segment.text.length;
}

function replaceTextRange(
  segments: ComposerSegment[],
  start: number,
  end: number,
  replacement: ComposerSegment[],
): ComposerSegment[] {
  const next: ComposerSegment[] = [];
  let cursor = 0;
  let inserted = false;

  for (const segment of segments) {
    const length = segmentLength(segment);
    const segmentStart = cursor;
    const segmentEnd = cursor + length;

    if (segmentEnd <= start || segmentStart >= end) {
      if (!inserted && segmentStart >= end) {
        next.push(...replacement);
        inserted = true;
      }
      next.push(segment);
      cursor = segmentEnd;
      continue;
    }

    if (segment.type === "text") {
      const keepBefore = Math.max(0, start - segmentStart);
      const keepAfter = Math.max(0, segmentEnd - end);
      if (keepBefore > 0) {
        next.push({ type: "text", text: segment.text.slice(0, keepBefore) });
      }
      if (!inserted) {
        next.push(...replacement);
        inserted = true;
      }
      if (keepAfter > 0) {
        next.push({ type: "text", text: segment.text.slice(segment.text.length - keepAfter) });
      }
    } else if (!inserted) {
      next.push(...replacement);
      inserted = true;
    }

    cursor = segmentEnd;
  }

  if (!inserted) {
    next.push(...replacement);
  }

  return normalizeSegments(next);
}

function normalizeSegments(segments: ComposerSegment[]): ComposerSegment[] {
  const next: ComposerSegment[] = [];
  for (const segment of segments) {
    if (segment.type === "text" && segment.text.length === 0) continue;
    const previous = next.at(-1);
    if (segment.type === "text" && previous?.type === "text") {
      previous.text += segment.text;
    } else {
      next.push(segment);
    }
  }
  return next.length > 0 ? next : [{ type: "text", text: "" }];
}
