import { Banknote, CalendarDays, Check, ChevronUp, X } from "lucide-react";
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
 * The chips sit inline on the assumptions row, before Edit costs, and open an
 * inline drawer in the profile-monogram idiom: a grid-rows reveal with a
 * header rule and Hide affordance, then the value with round confirm/cancel
 * controls. Below the tablet threshold the same form rides the short bottom
 * sheet. Submits go to the typed no-turn endpoint; the backend answers with a
 * superseding card, so this component never invents card state.
 *
 * The root renders `display: contents`, so the chips participate in the
 * surrounding assumptions flex row while the drawer spans its own full line.
 */

type DirectEditKind = "capital" | "dates";

type ConfirmationDirectEditControlsProps = {
  confirmation: StrategyConfirmationPayload;
  onDirectEdit: (edit: ConfirmationDirectEditPayload) => Promise<void>;
  t: TFunction;
};

const chipClassName =
  "inline-flex min-h-6 cursor-pointer items-center gap-1 rounded-full border border-black/10 bg-black/[0.02] px-2 py-0.5 text-[11px] font-medium text-black/60 transition-colors hover:border-black/18 hover:text-black/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/60 dark:hover:border-white/18 dark:hover:text-white/80";

// One inline-editing control vocabulary across capital, dates, and costs:
// compact round confirm/cancel icons, the same field shape, Enter applies
// and Escape cancels.
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
  const datesFieldLabel = t(
    "chat.confirmation.direct_edit.dates_label",
    "Dates",
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
    requestAnimationFrame(() => firstFieldRef.current?.focus());
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
    ) : (
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
    );

  const confirmControls = (
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
  );

  const form = (
    <div
      data-testid="confirmation-direct-edit-form"
      className="flex w-full flex-wrap items-end gap-x-3 gap-y-2"
    >
      {fields}
      {confirmControls}
      {error && (
        <p role="alert" className={`w-full text-[11px] ${inlineFailureTextClass}`}>
          {error}
        </p>
      )}
    </div>
  );

  const drawerHeading =
    openKind === "capital" ? capitalFieldLabel : datesFieldLabel;

  return (
    <div className="contents">
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
      {isBelowTablet ? (
        <BottomSheet
          isOpen={openKind !== null}
          onClose={close}
          title={drawerHeading}
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
          className={`grid basis-full transition-[grid-template-rows,margin,opacity] duration-200 ease-out motion-reduce:transition-none ${
            openKind !== null
              ? "mt-1 grid-rows-[1fr] opacity-100"
              : "mt-0 grid-rows-[0fr] opacity-0"
          }`}
          aria-hidden={openKind === null}
          inert={openKind === null}
        >
          <div className="min-h-0 overflow-hidden">
            <button
              type="button"
              onClick={close}
              data-testid="direct-edit-hide"
              className="flex h-9 w-full cursor-pointer items-center gap-2 text-[11px] font-medium uppercase tracking-[0.08em] text-[#8d969e] transition-colors hover:text-black/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:hover:text-white/70 dark:focus-visible:ring-white/22"
            >
              <span>{drawerHeading}</span>
              <span aria-hidden="true" className="h-px flex-1 bg-black/10 dark:bg-white/10" />
              <span className="normal-case tracking-normal">
                {t("chat.confirmation.direct_edit.hide", "Hide")}
              </span>
              <ChevronUp aria-hidden="true" className="h-3.5 w-3.5" />
            </button>
            <div className="pb-2">{form}</div>
          </div>
        </div>
      )}
    </div>
  );
}
