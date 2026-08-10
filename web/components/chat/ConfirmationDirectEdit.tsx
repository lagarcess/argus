import { Banknote, CalendarDays, Check, PencilLine, X } from "lucide-react";
import type { TFunction } from "i18next";
import { useRef, useState } from "react";
import { useResponsiveLayout } from "@/components/layout/useResponsiveLayout";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { inlineFailureTextClass } from "@/lib/failure-treatment";
import {
  MAX_SLIPPAGE_PERCENT,
  costEditDraftFromDisplayFacts,
  costEditDraftToRates,
  type ExecutionCostEditDraft,
} from "@/lib/confirmation-cost-edit";
import { ExecutionDetails } from "./ExecutionDetails";
import type {
  ConfirmationDirectEditPayload,
  StrategyConfirmationPayload,
} from "./types";

/**
 * In-place editing on the confirmation card (§3.4): capital, dates, and
 * costs, three affordances with one behaviour. Each is an ExecutionDetails
 * pill, the card vocabulary for inline disclosure, whose panel hosts the
 * editable fields; below the tablet threshold the same fields ride the
 * short bottom sheet. Submits go to the typed no-turn endpoint, which
 * updates the same card in place; this component never invents card state.
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

export function ConfirmationDirectEditControls({
  confirmation,
  onDirectEdit,
  t,
}: ConfirmationDirectEditControlsProps) {
  const { isBelowTablet } = useResponsiveLayout();
  const [openKind, setOpenKind] = useState<DirectEditKind | null>(null);
  const [capitalDraft, setCapitalDraft] = useState("");
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
  const canEditCapital = directEdits.includes("capital");
  const canEditDates = directEdits.includes("dates");
  const canEditCosts = directEdits.includes("costs");
  if (!canEditCapital && !canEditDates && !canEditCosts) {
    return null;
  }

  const isRecurring = confirmation.strategy_type === "dca_accumulation";
  const labels: Record<DirectEditKind, string> = {
    capital: isRecurring
      ? t("chat.confirmation.direct_edit.edit_contribution", "Edit contribution")
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
      const seed = confirmation.display_facts?.capital;
      setCapitalDraft(
        typeof seed === "number" && Number.isFinite(seed) ? String(seed) : "",
      );
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
      edit = { capital: amount };
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
      edit = { date_window: { start: startDraft, end: endDraft } };
    } else {
      const rates = costEditDraftToRates(costDraft);
      if (rates === null) {
        setError(
          t("chat.confirmation.cost_editor.invalid", {
            defaultValue:
              "Enter percentages of 0 or more (slippage up to {{max}}%).",
            max: MAX_SLIPPAGE_PERCENT,
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
    } catch {
      setIsSaving(false);
      setError(
        t(
          "chat.confirmation.direct_edit.failed",
          "That change did not go through. The card is unchanged.",
        ),
      );
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

  const fields =
    openKind === "capital" ? (
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
    ) : openKind === "dates" ? (
      <>
        <label className="flex flex-col gap-0.5 text-[11px] text-[#8d969e]">
          {t("chat.confirmation.direct_edit.start_label", "Start date")}
          <input
            ref={firstFieldRef}
            type="date"
            value={startDraft}
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

  const form = (
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
  );

  const kinds: { kind: DirectEditKind; enabled: boolean; icon: React.ReactNode }[] = [
    {
      kind: "capital",
      enabled: canEditCapital,
      icon: <Banknote aria-hidden="true" className="h-3 w-3" />,
    },
    {
      kind: "dates",
      enabled: canEditDates,
      icon: <CalendarDays aria-hidden="true" className="h-3 w-3" />,
    },
    {
      kind: "costs",
      enabled: canEditCosts,
      icon: <PencilLine aria-hidden="true" className="h-3 w-3" />,
    },
  ];

  return (
    <div className="contents">
      {kinds.map(({ kind, enabled, icon }) =>
        enabled ? (
          <ExecutionDetails
            key={kind}
            triggerLabel={labels[kind]}
            triggerIcon={icon}
            triggerTestId={`edit-${kind}`}
            panelTestId="confirmation-direct-edit-drawer"
            open={!isBelowTablet && openKind === kind}
            onToggle={() => toggle(kind)}
          >
            {form}
          </ExecutionDetails>
        ) : null,
      )}
      {isBelowTablet && (
        <BottomSheet
          isOpen={openKind !== null}
          onClose={close}
          title={openKind !== null ? labels[openKind] : ""}
          closeLabel={t("chat.confirmation.direct_edit.close", "Close")}
          height="short"
          initialFocusRef={firstFieldRef}
        >
          <div className="px-1 py-2">{form}</div>
        </BottomSheet>
      )}
    </div>
  );
}
