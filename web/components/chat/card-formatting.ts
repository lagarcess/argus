export type PeriodParts = {
  label: string;
  dates?: string;
};

export function splitPeriodDisplay(value: string): PeriodParts {
  const trimmed = value.trim();
  const parenthetical = trimmed.match(/^(.*?)\s*\((.*?)\)\s*$/);
  if (parenthetical) {
    return {
      label: parenthetical[1].trim(),
      dates: parenthetical[2].trim(),
    };
  }
  return { label: trimmed };
}

export function periodWithoutParentheses(value: string): string {
  const parts = splitPeriodDisplay(value);
  return parts.dates ? `${parts.label}, ${parts.dates}` : parts.label;
}

export function splitSymbolList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
