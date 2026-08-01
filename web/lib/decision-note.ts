export const DECISION_NOTE_MAX_LENGTH = 500;
export const DECISION_NOTE_COUNT_THRESHOLD = 450;

export function decisionNoteCountIsVisible(note: string): boolean {
  return Array.from(note).length >= DECISION_NOTE_COUNT_THRESHOLD;
}

export function decisionNoteCharacterCount(note: string): number {
  return Array.from(note).length;
}

export function nextDecisionNoteValue(current: string, next: string): string {
  const currentCharacters = Array.from(current);
  const nextCharacters = Array.from(next);
  if (nextCharacters.length <= DECISION_NOTE_MAX_LENGTH) return next;

  const currentCount = currentCharacters.length;
  if (currentCount > DECISION_NOTE_MAX_LENGTH) {
    return nextCharacters.length < currentCount ? next : current;
  }

  let prefixLength = 0;
  while (
    prefixLength < currentCharacters.length &&
    prefixLength < nextCharacters.length &&
    currentCharacters[prefixLength] === nextCharacters[prefixLength]
  ) {
    prefixLength += 1;
  }

  let currentSuffixStart = currentCharacters.length;
  let nextSuffixStart = nextCharacters.length;
  while (
    currentSuffixStart > prefixLength &&
    nextSuffixStart > prefixLength &&
    currentCharacters[currentSuffixStart - 1] ===
      nextCharacters[nextSuffixStart - 1]
  ) {
    currentSuffixStart -= 1;
    nextSuffixStart -= 1;
  }

  const retainedCharacters = [
    ...currentCharacters.slice(0, prefixLength),
    ...currentCharacters.slice(currentSuffixStart),
  ];
  const insertCapacity = DECISION_NOTE_MAX_LENGTH - retainedCharacters.length;
  const insertedCharacters = nextCharacters
    .slice(prefixLength, nextSuffixStart)
    .slice(0, Math.max(0, insertCapacity));

  return [
    ...currentCharacters.slice(0, prefixLength),
    ...insertedCharacters,
    ...currentCharacters.slice(currentSuffixStart),
  ].join("");
}
