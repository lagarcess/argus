import { Banknote, CalendarDays } from "lucide-react";
import type { TFunction } from "i18next";
import { useId, useRef, useState } from "react";
import { useResponsiveLayout } from "@/components/layout/useResponsiveLayout";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { inlineFailureTextClass } from "@/lib/failure-treatment";
import type {
  ConfirmationDirectEditPayload,
  StrategyConfirmationPayload,
} from "./types";

/**
 * Direct capital and date editing on the confirmation card (§3.4).
 *
 * A dedicated row in the shape of the edit-costs row opens an inline drawer on
 * wide screens and the short bottom sheet below the tablet threshold. Submits
 * go to the typed no-turn endpoint; the backend answers with a superseding
 * card, so this component never invents card state.
 */

type DirectEditKind = "capital" | "dates";

type ConfirmationDirectEditRowProps = {
  confirmation: StrategyConfirmationPayload;
  onDirectEdit: (edit: ConfirmationDirectEditPayload) => Promise<void>;
  t: TFunction;
};

const chipClassName =
  "inline-flex min-h-6 cursor-pointer items-center gap-1 rounded-full border border-black/10 bg-black/[0.02] px-2 py-0.5 text-[11px] font-medium text-black/60 transition-colors hover:border-black/18 hover:text-black/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/60 dark:hover:border-white/18 dark:hover:text-white/80";

const applyClassName =
  "inline-flex min-h-11 cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full border border-black/10 bg-black/[0.03] px-3.5 py-1.5 text-[13px] font-medium tracking-tight tablet:min-h-9 tablet:px-3 tablet:text-[12px] text-black/76 transition-colors hover:border-black/18 hover:bg-black/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 dark:border-white/10 dark:bg-white/[0.04] dark:text-white/76 dark:hover:border-white/18 dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/22";

export function ConfirmationDirectEditRow({
  confirmation,
  onDirectEdit,
  t,
}: ConfirmationDirectEditRowProps) {
  const { isBelowTablet } = useResponsiveLayout();
  const drawerId = useId();
  const [openKind, setOpenKind] = useState<DirectEditKind | null>(null);
  const [capitalDraft, setCapitalDraft] = useState("");
  const [startDraft, setStartDraft] = useState("");
  const [endDraft, setEndDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const firstFieldRef = useRef<HTMLInputElement | null>(null);

  const directEdits = confirmation.capabilities?.direct_edits ?? [];
  const canEditCapital = directEdits.includes("capital");
  const canEditDates = directEdits.includes("dates");
  if (!canEditCapital && !canEditDates) {
    return null;
  }

  const isRecurring = confirmation.strategy_type === "dca_accumulation";
  const capitalChipLabel = isRecurring
    ? t("chat.confirmation.direct_edit.edit_contribution", "Edit contribution")
    : t("chat.confirmation.direct_edit.edit_capital", "Edit capital");
  const capitalFieldLabel = isRecurring
    ? t("chat.confirmation.direct_edit.contribution_label", "Contribution")
    : t("chat.confirmation.direct_edit.capital_label", "Starting capital");
  const datesChipLabel = t(
    "chat.confirmation.direct_edit.edit_dates",
    "Edit dates",
  );

  const open = (kind: DirectEditKind) => {
    setError(null);
    if (kind === "capital") {
      const seed = confirmation.display_facts?.capital;
      setCapitalDraft(
        typeof seed === "number" && Number.isFinite(seed) ? String(seed) : "",
      );
    } else {
      setStartDraft(confirmation.date_range?.start ?? "");
      setEndDraft(confirmation.date_range?.end ?? "");
    }
    setOpenKind(kind);
  };

  const close = () => {
    if (isSaving) return;
    setOpenKind(null);
    setError(null);
  };

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
    } else {
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

  const form = (
    <div
      data-testid="confirmation-direct-edit-form"
      className="flex w-full flex-wrap items-end gap-2"
    >
      {openKind === "capital" ? (
        <label className="flex flex-col gap-0.5 text-[11px] text-[#8d969e]">
          {capitalFieldLabel}
          <input
            ref={firstFieldRef}
            type="text"
            inputMode="decimal"
            value={capitalDraft}
            onChange={(event) => setCapitalDraft(event.target.value)}
            data-testid="direct-edit-capital-input"
            className="h-10 w-32 rounded-md border border-black/12 bg-white px-2 text-[16px] text-[#191c1f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 tablet:h-8 tablet:text-[13px] dark:border-white/14 dark:bg-[#24282c] dark:text-white"
          />
        </label>
      ) : (
        <>
          <label className="flex flex-col gap-0.5 text-[11px] text-[#8d969e]">
            {t("chat.confirmation.direct_edit.start_label", "Start date")}
            <input
              ref={firstFieldRef}
              type="date"
              value={startDraft}
              onChange={(event) => setStartDraft(event.target.value)}
              data-testid="direct-edit-start-input"
              className="h-10 rounded-md border border-black/12 bg-white px-2 text-[16px] text-[#191c1f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 tablet:h-8 tablet:text-[13px] dark:border-white/14 dark:bg-[#24282c] dark:text-white"
            />
          </label>
          <label className="flex flex-col gap-0.5 text-[11px] text-[#8d969e]">
            {t("chat.confirmation.direct_edit.end_label", "End date")}
            <input
              type="date"
              value={endDraft}
              onChange={(event) => setEndDraft(event.target.value)}
              data-testid="direct-edit-end-input"
              className="h-10 rounded-md border border-black/12 bg-white px-2 text-[16px] text-[#191c1f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 tablet:h-8 tablet:text-[13px] dark:border-white/14 dark:bg-[#24282c] dark:text-white"
            />
          </label>
        </>
      )}
      <button
        type="button"
        onClick={() => void submit()}
        disabled={isSaving}
        aria-busy={isSaving}
        data-testid="direct-edit-apply"
        className={applyClassName}
      >
        {t("chat.confirmation.direct_edit.apply", "Apply")}
      </button>
      <button
        type="button"
        onClick={close}
        disabled={isSaving}
        data-testid="direct-edit-cancel"
        className={applyClassName}
      >
        {t("chat.confirmation.direct_edit.cancel", "Cancel")}
      </button>
      {error && (
        <p role="alert" className={`w-full text-[11px] ${inlineFailureTextClass}`}>
          {error}
        </p>
      )}
    </div>
  );

  const sheetTitle =
    openKind === "capital"
      ? capitalChipLabel
      : t("chat.confirmation.direct_edit.edit_dates", "Edit dates");

  return (
    <div data-testid="confirmation-direct-edit-row" className="w-full">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {canEditCapital && (
          <button
            type="button"
            data-testid="edit-capital"
            onClick={() => (openKind === "capital" ? close() : open("capital"))}
            aria-expanded={!isBelowTablet ? openKind === "capital" : undefined}
            aria-controls={!isBelowTablet ? drawerId : undefined}
            className={chipClassName}
          >
            <Banknote aria-hidden="true" className="h-3 w-3" />
            {capitalChipLabel}
          </button>
        )}
        {canEditDates && (
          <button
            type="button"
            data-testid="edit-dates"
            onClick={() => (openKind === "dates" ? close() : open("dates"))}
            aria-expanded={!isBelowTablet ? openKind === "dates" : undefined}
            aria-controls={!isBelowTablet ? drawerId : undefined}
            className={chipClassName}
          >
            <CalendarDays aria-hidden="true" className="h-3 w-3" />
            {datesChipLabel}
          </button>
        )}
      </div>
      {isBelowTablet ? (
        <BottomSheet
          isOpen={openKind !== null}
          onClose={close}
          title={sheetTitle}
          closeLabel={t("chat.confirmation.direct_edit.close", "Close")}
          height="short"
          initialFocusRef={firstFieldRef}
        >
          <div className="px-1 py-2">{form}</div>
        </BottomSheet>
      ) : (
        <div
          id={drawerId}
          data-testid="confirmation-direct-edit-drawer"
          className={`grid transition-[grid-template-rows,margin,opacity] duration-200 ease-out motion-reduce:transition-none ${
            openKind !== null
              ? "mt-2 grid-rows-[1fr] opacity-100"
              : "mt-0 grid-rows-[0fr] opacity-0"
          }`}
          aria-hidden={openKind === null}
          inert={openKind === null}
        >
          <div className="min-h-0 overflow-hidden">{form}</div>
        </div>
      )}
    </div>
  );
}
