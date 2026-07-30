import {
  PYTHON_ALPHANUMERIC_RANGES,
  PYTHON_CASEFOLD_EXPANSIONS,
  PYTHON_CASEFOLD_SINGLE_SOURCE,
  PYTHON_CASEFOLD_SINGLE_TARGET,
  PYTHON_CASEFOLD_UNICODE_VERSION,
} from "./search-casefold-data";

export { PYTHON_CASEFOLD_UNICODE_VERSION };

const singleSources = Array.from(PYTHON_CASEFOLD_SINGLE_SOURCE);
const singleTargets = Array.from(PYTHON_CASEFOLD_SINGLE_TARGET);
if (singleSources.length !== singleTargets.length) {
  throw new Error("Search casefold data is inconsistent.");
}

const casefoldMap = new Map<string, string>(
  singleSources.map((source, index) => [source, singleTargets[index]]),
);
for (const [source, target] of PYTHON_CASEFOLD_EXPANSIONS) {
  casefoldMap.set(source, target);
}

export function pythonCasefold(value: string): string {
  return Array.from(
    value,
    (character) => casefoldMap.get(character) ?? character,
  ).join("");
}

export function isPythonAlphanumeric(character: string): boolean {
  const codepoint = character.codePointAt(0);
  if (codepoint === undefined) return false;

  let low = 0;
  let high = PYTHON_ALPHANUMERIC_RANGES.length - 1;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    const [start, end] = PYTHON_ALPHANUMERIC_RANGES[middle];
    if (codepoint < start) {
      high = middle - 1;
    } else if (codepoint > end) {
      low = middle + 1;
    } else {
      return true;
    }
  }
  return false;
}

export type NormalizedSearchTokenSpan = {
  normalized: string;
  start: number;
  end: number;
};

export function normalizedSearchTokenSpans(
  value: string,
): NormalizedSearchTokenSpan[] {
  const spans: NormalizedSearchTokenSpan[] = [];
  let normalized = "";
  let tokenStart = 0;
  let tokenEnd = 0;
  let sourceOffset = 0;
  const flush = () => {
    if (!normalized) return;
    spans.push({ normalized, start: tokenStart, end: tokenEnd });
    normalized = "";
  };

  for (const sourceCharacter of value) {
    const sourceStart = sourceOffset;
    const sourceEnd = sourceStart + sourceCharacter.length;
    for (const foldedCharacter of pythonCasefold(sourceCharacter)) {
      if (isPythonAlphanumeric(foldedCharacter)) {
        if (!normalized) tokenStart = sourceStart;
        normalized += foldedCharacter;
        tokenEnd = sourceEnd;
      } else {
        flush();
      }
    }
    sourceOffset = sourceEnd;
  }
  flush();
  return spans;
}

export function normalizeSearchText(value: string): string {
  return normalizedSearchTokenSpans(value)
    .map((span) => span.normalized)
    .join(" ");
}

export function normalizedSearchTokens(value: string): string[] {
  const normalized = normalizeSearchText(value);
  return normalized ? normalized.split(" ") : [];
}

export const SEARCH_INDEXABLE_TOKEN_MIN_LENGTH = 3;

export function searchHasIndexableToken(value: string): boolean {
  return normalizedSearchTokens(value).some(
    (token) =>
      Array.from(token).length >= SEARCH_INDEXABLE_TOKEN_MIN_LENGTH,
  );
}
