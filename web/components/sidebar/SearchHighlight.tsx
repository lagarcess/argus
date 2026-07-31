import {
  normalizedSearchTokens,
  normalizedSearchTokenSpans,
} from "@/lib/search-text";

export function SearchHighlight({
  text,
  query,
}: {
  text: string;
  query: string;
}) {
  const queryTokens = Array.from(new Set(normalizedSearchTokens(query)));
  if (queryTokens.length === 0) return text;

  const highlightedSpans: Array<{ start: number; end: number }> = [];
  for (const span of normalizedSearchTokenSpans(text)) {
    if (!queryTokens.some((token) => span.normalized.includes(token))) continue;
    const previous = highlightedSpans.at(-1);
    if (previous && span.start <= previous.end) {
      previous.end = Math.max(previous.end, span.end);
    } else {
      highlightedSpans.push({ start: span.start, end: span.end });
    }
  }
  if (highlightedSpans.length === 0) return text;

  const parts: Array<{ text: string; highlighted: boolean }> = [];
  let cursor = 0;
  for (const span of highlightedSpans) {
    if (span.start > cursor) {
      parts.push({
        text: text.slice(cursor, span.start),
        highlighted: false,
      });
    }
    parts.push({
      text: text.slice(span.start, span.end),
      highlighted: true,
    });
    cursor = span.end;
  }
  if (cursor < text.length)
    parts.push({ text: text.slice(cursor), highlighted: false });

  return parts.map((part, index) =>
    part.highlighted ? (
      <mark
        key={`${index}-${part.text}`}
        className="rounded-sm bg-[#c2a44d]/20 px-0.5 font-semibold text-[#c2a44d]"
      >
        {part.text}
      </mark>
    ) : (
      <span key={`${index}-${part.text}`}>{part.text}</span>
    ),
  );
}
