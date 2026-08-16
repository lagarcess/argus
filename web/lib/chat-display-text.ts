export function normalizeAssistantDisplayText(content: string): string {
  return content
    .replace(/\b(?:1D|Daily) bars only\./g, "Daily data only.")
    // Both spellings: transcripts written before the rule was stated plainly
    // still carry the older sentence.
    .replace(
      /Recurring entries use the first available bar in each cadence window\./g,
      "Recurring entries use the first available daily price in each cadence window.",
    )
    .replace(
      /Each contribution buys at the first available bar in its period/g,
      "Each contribution buys at the first available daily price in its period",
    );
}
