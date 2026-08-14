import { Banknote, CalendarDays, Check, PencilLine, X } from "lucide-react";
import type { TFunction } from "i18next";
import { useRef, useState } from "react";
import { inlineFailureTextClass } from "@/lib/failure-treatment";
import { effectiveMaxEndDate } from "@/lib/date-edit-bounds";
import {
  MAX_SLIPPAGE_PERCENT,
  costEditDraftFromDisplayFacts,
  costEditDraftToRates,
  type ExecutionCostEditDraft,
} from "@/lib/confirmation-cost-edit";
import {
  ExecutionDetails,
  type ExecutionDetailsTrigger,
} from "./ExecutionDetails";
import type {
  ConfirmationDirectEditPayload,
  StrategyConfirmationPayload,
} from "./types";

/**
 * In-place editing on the confirmation card (§3.4): capital, dates, and
 * costs, three affordances with one behaviour at every width. The pills and
 * the open drawer are the ExecutionDetails idiom, expanding in flow inside
 * the card; the drawer sits under the pill row and pushes the actions down,
 * and the card never disappears. Submits go to the typed no-turn endpoint,
 * which updates the same card in place; this component never invents card
 * state.
 */

type DirectEditKind = "capital" | "dates" | "costs";

type ConfirmationDirectEditControlsProps = {
  confirmation: StrategyConfirmationPayload;
  onDirectEdit: (edit: ConfirmationDirectEditPayload) => Promise<void>;
  t: TFunction;
};

// One inline-editing control vocabulary: compact round confirm/cancel
// icons, the same field shape, Enter applies and Escape cancels.
export const inlineEditControlClassName =
  "inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full border border-black/10 bg-black/[0.03] text-black/70 transition-colors hover:border-black/18 hover:bg-black/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-45 dark:border-white/10 dark:bg-white/[0.04] dark:text-white/70 dark:hover:border-white/18 dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/22";

export const inlineEditFieldClassName =
  "h-9 rounded-lg border border-black/12 bg-white px-2.5 text-[16px] text-[#191c1f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 tablet:h-8 tablet:text-[13px] dark:border-white/14 dark:bg-[#24282c] dark:text-white";

/** Localized copy for the backend's typed refusals. Codes are the
 * envelope's own vocabulary; anything unknown falls back to the generic
 * failure line. */
function directEditErrorText(
  code: string,
  t: TFunction,
  constraints: NonNullable<
    StrategyConfirmationPayload["capabilities"]
  >["edit_constraints"],
  isRecurring = false,
): string {
  const capitalMin = constraints?.capital?.min;
  const capitalMax = constraints?.capital?.max;
  const money = (value: number | undefined, fallback: string) =>
    typeof value === "number" ? `$${value.toLocaleString()}` : fallback;
  switch (code) {
    case "invalid_recurring_contribution":
      return t("chat.confirmation.direct_edit.errors.invalid_contribution", {
        defaultValue: "Each contribution must be between {{min}} and {{max}}.",
        min: money(constraints?.contribution?.min, "$0"),
        max: money(constraints?.contribution?.max, "$100,000,000"),
      });
    case "dca_requires_starting_capital_or_contribution":
      return t(
        "chat.confirmation.direct_edit.errors.dca_needs_money",
        "Set a starting capital, a contribution, or both.",
      );
    case "dca_contribution_zero_is_buy_and_hold":
      return t(
        "chat.confirmation.direct_edit.errors.dca_contribution_zero",
        "With no contribution this is a buy and hold of the starting capital. Add a contribution, or test it as buy and hold.",
      );
    case "contribution_period_exceeds_window":
      return t(
        "chat.confirmation.direct_edit.errors.contribution_period_exceeds_window",
        "That period does not fit inside the tested dates. Pick a shorter period or a longer date range.",
      );
    case "invalid_starting_capital":
      // The engine runs a recurring contribution through the same band, so
      // the refusal names whichever money role this card edits.
      return isRecurring
        ? t("chat.confirmation.direct_edit.errors.invalid_seed", {
            defaultValue: "Starting capital must be between {{min}} and {{max}}.",
            min: money(constraints?.starting_capital?.min, "$0"),
            max: money(constraints?.starting_capital?.max, "$100,000,000"),
          })
        : t("chat.confirmation.direct_edit.errors.invalid_starting_capital", {
            defaultValue:
              "Starting capital must be between {{min}} and {{max}}.",
            min: money(capitalMin, "$1,000"),
            max: money(capitalMax, "$100,000,000"),
          });
    case "future_end_date":
      return t(
        "chat.confirmation.direct_edit.errors.future_end_date",
        "Pick an end date on or before today.",
      );
    case "invalid_chronological_date_range":
      return t(
        "chat.confirmation.direct_edit.errors.invalid_chronological_date_range",
        "Pick a start date before the end date.",
      );
    case "provider_history_start_unavailable":
      return t("chat.confirmation.direct_edit.errors.provider_history_start", {
        defaultValue:
          "Data for this test starts later; pick a start date on or after {{min}}.",
        min: constraints?.date_window?.min_start ?? "2016-01-01",
      });
    case "no_common_data_window":
    case "insufficient_common_data":
      return t(
        "chat.confirmation.direct_edit.errors.no_common_data",
        "These assets do not share enough data for that window.",
      );
    case "unsupported_cost_value":
      return t("chat.confirmation.cost_editor.invalid", {
        defaultValue:
          "Enter percentages of 0 or more (slippage up to {{max}}%).",
        max: MAX_SLIPPAGE_PERCENT,
      });
    case "confirmation_changed":
      return t(
        "chat.confirmation.direct_edit.errors.confirmation_changed",
        "Another change landed at the same time. Try again.",
      );
    default:
      return t(
        "chat.confirmation.direct_edit.failed",
        "That change did not go through. The card is unchanged.",
      );
  }
}

export function ConfirmationDirectEditControls({
  confirmation,
  onDirectEdit,
  t,
}: ConfirmationDirectEditControlsProps) {
  const [openKind, setOpenKind] = useState<DirectEditKind | null>(null);
  const [capitalDraft, setCapitalDraft] = useState("");
  const [seedDraft, setSeedDraft] = useState("");
  const [periodDraft, setPeriodDraft] = useState("");
  const [startDraft, setStartDraft] = useState("");
  const [endDraft, setEndDraft] = useState("");
  const [costDraft, setCostDraft] = useState<ExecutionCostEditDraft>({
    feePercent: "0",
    slippagePercent: "0",
  });
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const firstFieldRef = useRef<HTMLInputElement | null>(null);

  const directEdits = confirmation.capabilities?.direct_edits ?? [];
  const constraints = confirmation.capabilities?.edit_constraints;
  // A backtest tests the past: no card may offer a date after today, with or
  // without an advertised envelope, and the picker itself must say so.
  const maxEndDate = effectiveMaxEndDate(constraints?.date_window?.max_end);
  const canEditCapital = directEdits.includes("capital");
  const canEditDates = directEdits.includes("dates");
  const canEditCosts = directEdits.includes("costs");
  if (!canEditCapital && !canEditDates && !canEditCosts) {
    return null;
  }

  const isRecurring = confirmation.strategy_type === "dca_accumulation";
  // Backend truth: the only periods this card's window can hold. The picker
  // renders exactly these, plus the card's own period when the served window
  // no longer holds it, because showing the run's actual period is honest and
  // silently swapping it for another is not. The backend still refuses a
  // period that cannot fit, naming the rule.
  const offeredPeriods = constraints?.contribution?.periods ?? [];
  const cardPeriod = confirmation.display_facts?.contribution_period ?? "";
  const periodOptions =
    cardPeriod && !offeredPeriods.includes(cardPeriod)
      ? [cardPeriod, ...offeredPeriods]
      : offeredPeriods;
  const labels: Record<DirectEditKind, string> = {
    capital: isRecurring
      ? t("chat.confirmation.direct_edit.edit_money", "Edit amounts")
      : t("chat.confirmation.direct_edit.edit_capital", "Edit capital"),
    dates: t("chat.confirmation.direct_edit.edit_dates", "Edit dates"),
    costs: t("chat.confirmation.direct_edit.edit_costs", "Edit costs"),
  };
  const capitalFieldLabel = isRecurring
    ? t("chat.confirmation.direct_edit.contribution_label", "Contribution")
    : t("chat.confirmation.direct_edit.capital_label", "Starting capital");

  const open = (kind: DirectEditKind) => {
    setError(null);
    if (kind === "capital") {
      const facts = confirmation.display_facts;
      const seed = isRecurring ? facts?.recurring_contribution : facts?.capital;
      setCapitalDraft(
        typeof seed === "number" && Number.isFinite(seed) ? String(seed) : "",
      );
      const startingCapital = facts?.starting_capital;
      setSeedDraft(
        typeof startingCapital === "number" && Number.isFinite(startingCapital)
          ? String(startingCapital)
          : "0",
      );
      // The card's own period, never another one chosen on the user's behalf.
      setPeriodDraft(facts?.contribution_period ?? periodOptions[0] ?? "");
    } else if (kind === "dates") {
      setStartDraft(confirmation.date_range?.start ?? "");
      setEndDraft(confirmation.date_range?.end ?? "");
    } else {
      setCostDraft(costEditDraftFromDisplayFacts(confirmation.display_facts));
    }
    setOpenKind(kind);
    requestAnimationFrame(() => firstFieldRef.current?.focus());
  };

  const close = () => {
    if (isSaving) return;
    setOpenKind(null);
    setError(null);
  };

  const toggle = (kind: DirectEditKind) =>
    openKind === kind ? close() : open(kind);

  const submit = async () => {
    if (openKind === null || isSaving) return;
    let edit: ConfirmationDirectEditPayload;
    if (openKind === "capital") {
      const amount = Number(capitalDraft.replace(/[\s,$]/g, ""));
      if (!Number.isFinite(amount) || amount <= 0) {
        setError(
          t(
            "chat.confirmation.direct_edit.invalid_capital",
            "Enter an amount above zero.",
          ),
        );
        return;
      }
      const band = isRecurring ? constraints?.contribution : constraints?.capital;
      if (
        (typeof band?.min === "number" && amount < band.min) ||
        (typeof band?.max === "number" && amount > band.max)
      ) {
        setError(
          directEditErrorText(
            isRecurring
              ? "invalid_recurring_contribution"
              : "invalid_starting_capital",
            t,
            constraints,
            isRecurring,
          ),
        );
        return;
      }
      if (!isRecurring) {
        edit = { capital: amount };
      } else {
        // Starting capital is its own role and $0 is its default, so an empty
        // field means no seed rather than an unset value to guess at.
        const seed = Number((seedDraft || "0").replace(/[\s,$]/g, ""));
        const seedMax = constraints?.starting_capital?.max;
        if (
          !Number.isFinite(seed) ||
          seed < 0 ||
          (typeof seedMax === "number" && seed > seedMax)
        ) {
          setError(
            directEditErrorText("invalid_starting_capital", t, constraints, true),
          );
          return;
        }
        edit = {
          starting_capital: seed,
          recurring_contribution: amount,
          ...(periodDraft ? { contribution_period: periodDraft } : {}),
        };
      }
    } else if (openKind === "dates") {
      if (!startDraft || !endDraft || startDraft > endDraft) {
        setError(
          t(
            "chat.confirmation.direct_edit.invalid_dates",
            "Pick a start date on or before the end date.",
          ),
        );
        return;
      }
      if (endDraft > maxEndDate || startDraft > maxEndDate) {
        setError(directEditErrorText("future_end_date", t, constraints));
        return;
      }
      const minStart = constraints?.date_window?.min_start;
      if (typeof minStart === "string" && minStart && startDraft < minStart) {
        setError(
          directEditErrorText("provider_history_start_unavailable", t, constraints),
        );
        return;
      }
      edit = { date_window: { start: startDraft, end: endDraft } };
    } else {
      const rates = costEditDraftToRates(costDraft, {
        feeMaxPercent:
          typeof constraints?.fees?.max === "number"
            ? constraints.fees.max * 100
            : undefined,
        slippageMaxPercent:
          typeof constraints?.slippage?.max === "number"
            ? constraints.slippage.max * 100
            : undefined,
      });
      if (rates === null) {
        setError(
          t("chat.confirmation.cost_editor.invalid", {
            defaultValue:
              "Enter percentages of 0 or more (slippage up to {{max}}%).",
            max:
              typeof constraints?.slippage?.max === "number"
                ? constraints.slippage.max * 100
                : MAX_SLIPPAGE_PERCENT,
          }),
        );
        return;
      }
      edit = rates;
    }
    setIsSaving(true);
    setError(null);
    try {
      await onDirectEdit(edit);
      setIsSaving(false);
      setOpenKind(null);
    } catch (submitError) {
      setIsSaving(false);
      const code = String(
        (submitError as { code?: unknown } | null)?.code ?? "",
      );
      setError(directEditErrorText(code, t, constraints, isRecurring));
    }
  };

  const onFieldKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void submit();
    } else if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
  };

  const contributionField = (
    <label className="flex flex-col gap-0.5 text-[11px] text-[#8d969e]">
      {capitalFieldLabel}
      <span className="flex flex-wrap items-center gap-1.5">
        <span aria-hidden="true" className="text-[13px] text-[#8d969e]">
          $
        </span>
        <input
          ref={isRecurring ? undefined : firstFieldRef}
          type="text"
          inputMode="decimal"
          value={capitalDraft}
          onChange={(event) => setCapitalDraft(event.target.value)}
          onKeyDown={onFieldKeyDown}
          data-testid="direct-edit-capital-input"
          className={`${inlineEditFieldClassName} w-24 tablet:w-28`}
        />
        {isRecurring && periodOptions.length > 0 && (
          <select
            value={periodDraft}
            onChange={(event) => setPeriodDraft(event.target.value)}
            aria-label={t(
              "chat.confirmation.direct_edit.period_label",
              "How often",
            )}
            data-testid="direct-edit-period-select"
            className={`${inlineEditFieldClassName} w-32`}
          >
            {periodOptions.map((option) => (
              <option key={option} value={option}>
                {t(
                  `chat.confirmation.contribution_periods.${option}`,
                  option.replace(/_/g, " "),
                )}
              </option>
            ))}
          </select>
        )}
      </span>
    </label>
  );

  const fields =
    openKind === "capital" ? (
      isRecurring ? (
        <>
          <label className="flex flex-col gap-0.5 text-[11px] text-[#8d969e]">
            {t(
              "chat.confirmation.direct_edit.starting_capital_label",
              "Starting capital",
            )}
            <span className="flex items-center gap-1.5">
              <span aria-hidden="true" className="text-[13px] text-[#8d969e]">
                $
              </span>
              <input
                ref={firstFieldRef}
                type="text"
                inputMode="decimal"
                value={seedDraft}
                onChange={(event) => setSeedDraft(event.target.value)}
                onKeyDown={onFieldKeyDown}
                data-testid="direct-edit-starting-capital-input"
                className={`${inlineEditFieldClassName} w-36 tablet:w-28`}
              />
            </span>
          </label>
          {contributionField}
        </>
      ) : (
        <label className="flex items-center gap-1.5">
          <span className="sr-only">{capitalFieldLabel}</span>
          <span aria-hidden="true" className="text-[13px] text-[#8d969e]">
            $
          </span>
          <input
            ref={firstFieldRef}
            type="text"
            inputMode="decimal"
            value={capitalDraft}
            onChange={(event) => setCapitalDraft(event.target.value)}
            onKeyDown={onFieldKeyDown}
            data-testid="direct-edit-capital-input"
            className={`${inlineEditFieldClassName} w-36 tablet:w-28`}
          />
        </label>
      )
    ) : openKind === "dates" ? (
      <>
        <label className="flex flex-col gap-0.5 text-[11px] text-[#8d969e]">
          {t("chat.confirmation.direct_edit.start_label", "Start date")}
          <input
            ref={firstFieldRef}
            type="date"
            value={startDraft}
            min={constraints?.date_window?.min_start}
            max={maxEndDate}
            onChange={(event) => setStartDraft(event.target.value)}
            onKeyDown={onFieldKeyDown}
            data-testid="direct-edit-start-input"
            className={inlineEditFieldClassName}
          />
        </label>
        <label className="flex flex-col gap-0.5 text-[11px] text-[#8d969e]">
          {t("chat.confirmation.direct_edit.end_label", "End date")}
          <input
            type="date"
            value={endDraft}
            min={constraints?.date_window?.min_start}
            max={maxEndDate}
            onChange={(event) => setEndDraft(event.target.value)}
            onKeyDown={onFieldKeyDown}
            data-testid="direct-edit-end-input"
            className={inlineEditFieldClassName}
          />
        </label>
      </>
    ) : (
      <>
        <label className="flex flex-col gap-0.5 text-[11px] text-[#8d969e]">
          {t("chat.confirmation.cost_editor.fee_label", "Fee % per trade")}
          <input
            ref={firstFieldRef}
            type="text"
            inputMode="decimal"
            value={costDraft.feePercent}
            onChange={(event) =>
              setCostDraft((prev) => ({ ...prev, feePercent: event.target.value }))
            }
            onKeyDown={onFieldKeyDown}
            data-testid="direct-edit-fee-input"
            className={`${inlineEditFieldClassName} w-24`}
          />
        </label>
        <label className="flex flex-col gap-0.5 text-[11px] text-[#8d969e]">
          {t("chat.confirmation.cost_editor.slippage_label", "Slippage % per trade")}
          <input
            type="text"
            inputMode="decimal"
            value={costDraft.slippagePercent}
            onChange={(event) =>
              setCostDraft((prev) => ({
                ...prev,
                slippagePercent: event.target.value,
              }))
            }
            onKeyDown={onFieldKeyDown}
            data-testid="direct-edit-slippage-input"
            className={`${inlineEditFieldClassName} w-24`}
          />
        </label>
      </>
    );

  const triggers: ExecutionDetailsTrigger[] = [
    canEditCapital && {
      key: "capital",
      label: labels.capital,
      icon: <Banknote aria-hidden="true" className="h-3 w-3" />,
      testId: "edit-capital",
    },
    canEditDates && {
      key: "dates",
      label: labels.dates,
      icon: <CalendarDays aria-hidden="true" className="h-3 w-3" />,
      testId: "edit-dates",
    },
    canEditCosts && {
      key: "costs",
      label: labels.costs,
      icon: <PencilLine aria-hidden="true" className="h-3 w-3" />,
      testId: "edit-costs",
    },
  ].filter(Boolean) as ExecutionDetailsTrigger[];

  return (
    <ExecutionDetails
      triggers={triggers}
      openKey={openKind}
      onToggle={(key) => toggle(key as DirectEditKind)}
      panelTestId="confirmation-direct-edit-drawer"
    >
      <div
        data-testid="confirmation-direct-edit-form"
        className="flex w-full flex-wrap items-end gap-x-3 gap-y-2"
      >
        {fields}
        <div className="flex items-center gap-1.5 self-end pb-0.5">
          <button
            type="button"
            onClick={() => void submit()}
            disabled={isSaving}
            aria-busy={isSaving}
            aria-label={t("chat.confirmation.direct_edit.apply", "Apply")}
            data-testid="direct-edit-apply"
            className={inlineEditControlClassName}
          >
            <Check aria-hidden="true" className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={close}
            disabled={isSaving}
            aria-label={t("chat.confirmation.direct_edit.cancel", "Cancel")}
            data-testid="direct-edit-cancel"
            className={inlineEditControlClassName}
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>
        {error && (
          <p role="alert" className={`w-full text-[11px] ${inlineFailureTextClass}`}>
            {error}
          </p>
        )}
      </div>
    </ExecutionDetails>
  );
}
