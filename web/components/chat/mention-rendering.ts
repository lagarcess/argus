import type { ChatMention } from "./types";

export type MessageMentionPiece =
  | { kind: "text"; text: string }
  | { kind: "mention"; mention: ChatMention; text: string };

export function messageMentionPieces(
  content: string,
  mentions: ChatMention[],
): MessageMentionPiece[] {
  if (mentions.length === 0) return [{ kind: "text", text: content }];
  return exactMentionPieces(content, mentions) ?? legacyMentionPieces(content, mentions);
}

function exactMentionPieces(
  content: string,
  mentions: ChatMention[],
): MessageMentionPiece[] | null {
  const ranges = mentions
    .map((mention) => ({ mention, range: mention.message_range }))
    .sort((left, right) => (left.range?.start ?? 0) - (right.range?.start ?? 0));
  if (
    ranges.some(({ mention, range }) =>
      !range ||
      !Number.isInteger(range.start) ||
      !Number.isInteger(range.end) ||
      range.start < 0 ||
      range.end <= range.start ||
      range.end > content.length ||
      content.slice(range.start, range.end) !== mention.insert_text,
    )
  ) {
    return null;
  }

  const pieces: MessageMentionPiece[] = [];
  let cursor = 0;
  for (const { mention, range } of ranges) {
    if (!range || range.start < cursor) return null;
    if (range.start > cursor) {
      pieces.push({ kind: "text", text: content.slice(cursor, range.start) });
    }
    pieces.push({
      kind: "mention",
      mention,
      text: content.slice(range.start, range.end),
    });
    cursor = range.end;
  }
  if (cursor < content.length) {
    pieces.push({ kind: "text", text: content.slice(cursor) });
  }
  return pieces;
}

function legacyMentionPieces(
  content: string,
  mentions: ChatMention[],
): MessageMentionPiece[] {
  const pieces: MessageMentionPiece[] = [];
  const remainingMentions = [...mentions];
  let cursor = 0;

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
        .sort((left, right) => right.length - left.length);
      for (const candidate of candidates) {
        const index = content.indexOf(candidate, cursor);
        if (index < 0) continue;
        if (nextMatch === null || index < nextMatch.index) {
          nextMatch = { index, mention, text: candidate, mentionIndex };
        }
      }
    }
    if (nextMatch === null) {
      pieces.push({ kind: "text", text: content.slice(cursor) });
      break;
    }
    if (nextMatch.index > cursor) {
      pieces.push({ kind: "text", text: content.slice(cursor, nextMatch.index) });
    }
    pieces.push({ kind: "mention", mention: nextMatch.mention, text: nextMatch.text });
    cursor = nextMatch.index + nextMatch.text.length;
    remainingMentions.splice(nextMatch.mentionIndex, 1);
  }
  return pieces;
}
