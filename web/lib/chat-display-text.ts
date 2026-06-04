export function normalizeAssistantDisplayText(content: string): string {
  return content
    .replace(/\b(?:1D|Daily) bars only\./g, "Daily data only.")
    .replace(
      /Recurring entries use the first available bar in each cadence window\./g,
      "Recurring entries use the first available daily price in each cadence window.",
    );
}
