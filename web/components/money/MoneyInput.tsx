"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  currencySymbol,
  editMoney,
  formatMoney,
  localeUsesCommaDecimal,
  moneyPlaceholder,
  moneyProblemFromServer,
  parsePasted,
  readMoney,
  group,
  logicalIndex,
  displayIndex,
  type MoneyEditInput,
  type MoneyProblem,
  type MoneyRules,
} from "@/lib/money-entry";

export type MoneyInputChange = { value: string | null; invalid: boolean };

type MoneyInputProps = {
  /** The field's name without the currency; the accessible label adds it. */
  label: string;
  /** ISO code; empty while the user has not chosen one. */
  currency: string;
  /** Canonical dot-decimal value, or null for empty. */
  value: string | null;
  onValueChange: (change: MoneyInputChange) => void;
  allowNegative?: boolean;
  disabled?: boolean;
  /** A backend recording error code such as amount_precision. */
  serverError?: string | null;
  testId?: string;
};

const INSERTS = new Set(["insertText", "insertReplacementText", "insertFromPaste", "insertFromDrop", "insertFromYank"]);
const DELETES: Record<string, "backward" | "forward"> = {
  deleteContentBackward: "backward",
  deleteContentForward: "forward",
  deleteByCut: "backward",
  deleteByDrag: "backward",
  deleteContent: "backward",
};

function displayFor(value: string | null, rules: MoneyRules): string {
  if (!value) return "";
  const parsed = parsePasted(value, rules);
  return "logical" in parsed ? formatMoney(group(parsed.logical), rules) : value;
}

export default function MoneyInput({
  label,
  currency,
  value,
  onValueChange,
  allowNegative = false,
  disabled = false,
  serverError = null,
  testId,
}: MoneyInputProps) {
  const { t } = useTranslation();
  const id = useId();
  const messageId = `${id}-message`;
  const inputRef = useRef<HTMLInputElement>(null);
  const pendingCaret = useRef<number | null>(null);
  const rulesFor = (code: string): MoneyRules => ({
    currency: code,
    allowNegative,
    commaDecimal: typeof navigator !== "undefined" && localeUsesCommaDecimal(navigator.language),
  });
  const rules = rulesFor(currency);
  const [text, setText] = useState(() => displayFor(value, rules));
  const [problem, setProblem] = useState<MoneyProblem | null>(null);

  // A value the parent sets that this text does not already read as (a reload,
  // a server correction) replaces the text; echoes of our own emits do not.
  const [seenValue, setSeenValue] = useState(value);
  if (value !== seenValue) {
    setSeenValue(value);
    if (value !== readMoney(text, rules).value) {
      setText(displayFor(value, rules));
      setProblem(null);
    }
  }

  const commit = (next: string, caret: number | null, nextProblem: MoneyProblem | null) => {
    pendingCaret.current = caret;
    setText(next);
    setProblem(nextProblem);
    const reading = readMoney(next, rules);
    onValueChange({ value: reading.value, invalid: reading.problem !== null });
  };

  // The native beforeinput listener is attached once and reads the current render through this ref.
  const latest = useRef({ text, rules, onValueChange, commit });
  useLayoutEffect(() => {
    latest.current = { text, rules, onValueChange, commit };
  });

  // A currency change revalidates the same digits; there is no conversion.
  const seenCurrency = useRef(currency);
  useEffect(() => {
    if (seenCurrency.current === currency) return;
    seenCurrency.current = currency;
    const reading = readMoney(latest.current.text, latest.current.rules);
    setProblem(reading.problem?.code === "precision" ? reading.problem : null);
    latest.current.onValueChange({ value: reading.value, invalid: reading.problem !== null });
  }, [currency]);

  useLayoutEffect(() => {
    const input = inputRef.current;
    if (pendingCaret.current === null || !input || document.activeElement !== input) return;
    input.setSelectionRange(pendingCaret.current, pendingCaret.current);
    pendingCaret.current = null;
  });

  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    const onBeforeInput = (event: InputEvent) => {
      if (event.isComposing) return;
      let edit: MoneyEditInput;
      if (INSERTS.has(event.inputType)) {
        edit = { type: "insert", text: event.data ?? event.dataTransfer?.getData("text/plain") ?? "" };
      } else if (DELETES[event.inputType]) {
        edit = { type: "delete", direction: DELETES[event.inputType] };
      } else {
        return;
      }
      event.preventDefault();
      const { text: current, rules: currentRules, commit: apply } = latest.current;
      const start = input.selectionStart ?? current.length;
      const end = input.selectionEnd ?? start;
      const result = editMoney(current, start, end, edit, currentRules);
      if (result.kind === "accept") apply(result.display, result.caret, result.problem);
      else if (result.kind === "reject") setProblem(result.problem);
    };
    input.addEventListener("beforeinput", onBeforeInput);
    return () => input.removeEventListener("beforeinput", onBeforeInput);
  }, []);

  // Edits the browser does not announce as cancellable (word deletion, undo,
  // IME commits) arrive here and are validated whole, like a paste.
  const onChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const raw = event.target.value;
    const caret = event.target.selectionStart ?? raw.length;
    const parsed = raw.trim() ? parsePasted(raw, rules) : { logical: "" };
    if ("problem" in parsed) {
      setProblem(parsed.problem);
      return;
    }
    const next = group(parsed.logical);
    commit(next, displayIndex(next, logicalIndex(raw, caret)), null);
  };

  const onBlur = () => {
    const reading = readMoney(text, rules);
    if (reading.problem) {
      setProblem(reading.problem);
      return;
    }
    const formatted = formatMoney(text, rules);
    if (formatted !== text) commit(formatted, null, null);
  };

  const shown = problem ?? moneyProblemFromServer(serverError, currency);
  const symbol = currencySymbol(currency);
  const accessibleLabel = currency
    ? t("money.label", "{{label}} in {{currency}}", { label, currency: symbol === currency ? currency : `${currency} (${symbol})` })
    : label;

  return (
    <div>
      <div
        className={`mt-1.5 flex min-h-11 w-full items-center gap-2 rounded-[12px] border bg-white px-3 transition-colors focus-within:ring-[0.125rem] dark:bg-[#141517] ${
          shown
            ? "border-[#a8434c]/60 focus-within:ring-[#a8434c]/15 dark:border-[#ec9aa0]/60"
            : "border-black/10 focus-within:border-black/30 focus-within:ring-black/10 dark:border-white/10"
        } ${disabled ? "bg-black/[0.03] dark:bg-white/[0.03]" : ""}`}
      >
        {symbol ? (
          <span aria-hidden="true" className="shrink-0 text-[16px] tabular-nums text-black/50 dark:text-white/50">
            {symbol}
          </span>
        ) : null}
        <input
          ref={inputRef}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          spellCheck={false}
          className="min-w-0 flex-1 bg-transparent py-2 text-[16px] tabular-nums text-black outline-none placeholder:text-black/30 disabled:text-black/50 dark:text-white dark:placeholder:text-white/30"
          value={text}
          placeholder={moneyPlaceholder(currency)}
          onChange={onChange}
          onBlur={onBlur}
          disabled={disabled}
          aria-label={accessibleLabel}
          aria-invalid={shown ? true : undefined}
          aria-describedby={messageId}
          data-testid={testId}
        />
      </div>
      <p id={messageId} aria-live="polite" className={shown ? "mt-1 text-[13px] text-[#a8434c] dark:text-[#ec9aa0]" : ""}>
        {shown ? moneyMessage(shown, t) : ""}
      </p>
    </div>
  );
}

type Translate = ReturnType<typeof useTranslation>["t"];

function moneyMessage(problem: MoneyProblem, t: Translate): string {
  switch (problem.code) {
    case "invalid":
      return t("money.invalid", "Use digits and one decimal point.");
    case "decimal_twice":
      return t("money.decimal_twice", "An amount has only one decimal point.");
    case "negative":
      return t("money.negative", "Enter a positive amount.");
    case "grouping":
      return t("money.grouping", "Check the thousands commas, as in 1,250.50.");
    case "decimal_comma":
      return t("money.decimal_comma", "Use a point for decimals, as in 1,250.50.");
    case "precision":
      return problem.digits === 0
        ? t("money.precision_none", "{{currency}} has no decimals.", { currency: problem.currency })
        : t("money.precision", "{{currency}} allows up to {{count}} decimals.", { currency: problem.currency, count: problem.digits });
    case "maximum":
      return t("money.maximum", "The maximum is {{maximum}}.", { maximum: problem.maximum });
    case "currency_mismatch":
      return t("money.currency_mismatch", "This amount is in {{field}}, not {{typed}}.", {
        field: problem.field,
        typed: problem.typed,
      });
    case "zero":
      return t("money.zero", "Enter an amount greater than 0.");
  }
}
