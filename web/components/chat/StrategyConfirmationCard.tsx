import {
  CalendarDays,
  Check,
  CheckCircle2,
  CircleSlash2,
  type LucideIcon,
  Loader2,
  Pencil,
  PencilLine,
  Play,
  RefreshCw,
  Search,
  Send,
  SlidersHorizontal,
  TriangleAlert,
  X,
} from "lucide-react";
import type { TFunction } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  artifactLifecycleTone,
  artifactStatusToneClassName,
  type ArtifactStatusTone,
} from "@/lib/artifact-status-tones";
import { compactDateRangeDisplay } from "@/lib/date-range-display";
import {
  confirmationCardViewModel,
  type ConfirmationCardRow,
} from "@/lib/confirmation-card-view-model";
import {
  retestEffectiveDurationLabel,
  retestPeriodTransformationLabel,
  type RetestPeriod,
} from "@/lib/chat-retest";
import {
  type ChatActionOption,
  type ConfirmationDirectEditPayload,
  type StrategyConfirmationPayload,
  type StrategyConfirmationStatus,
} from "./types";
import {
  ConfirmationDirectEditControls,
  inlineEditControlClassName,
  inlineEditFieldClassName,
} from "./ConfirmationDirectEdit";
import { splitPeriodDisplay } from "./card-formatting";
import { EntityToken } from "./entity-token";
import { inlineFailureTextClass } from "@/lib/failure-treatment";
import {
  confirmationActionLabelKey,
  confirmationStatusAllowsActions,
  confirmationStatusFromPayload,
  confirmationStatusLabel,
  confirmationStatusLabelKey,
} from "./confirmation-display";

type StrategyConfirmationCardProps = {
  confirmation: StrategyConfirmationPayload;
  onAction?: (action: ChatActionOption) => void;
  onDirectEdit?: (edit: ConfirmationDirectEditPayload) => Promise<void>;
};

type ConfirmationStatusIconState = {
  icon: LucideIcon;
  isSpinning: boolean;
};

const CONFIRMATION_STATUS_ICON_STATE = {
  could_not_run: { icon: TriangleAlert, isSpinning: false },
  draft_canceled: { icon: CircleSlash2, isSpinning: false },
  editing: { icon: Pencil, isSpinning: false },
  needs_change: { icon: SlidersHorizontal, isSpinning: false },
  not_completed: { icon: CircleSlash2, isSpinning: false },
  ready_to_run: { icon: Play, isSpinning: false },
  request_sent: { icon: Send, isSpinning: false },
  run_complete: { icon: CheckCircle2, isSpinning: false },
  running: { icon: Loader2, isSpinning: true },
  updated: { icon: RefreshCw, isSpinning: false },
} satisfies Record<StrategyConfirmationStatus, ConfirmationStatusIconState>;

const actionClassName =
  "inline-flex min-h-11 cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full border border-black/10 bg-black/[0.03] px-3.5 py-1.5 text-[13px] font-medium tracking-tight tablet:min-h-9 tablet:px-3 tablet:text-[12px] text-black/76 transition-colors hover:border-black/18 hover:bg-black/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 active:scale-[0.98] dark:border-white/10 dark:bg-white/[0.04] dark:text-white/76 dark:hover:border-white/18 dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/22";

const TERMINAL_CONFIRMATION_STATUSES = new Set<StrategyConfirmationStatus>([
  "could_not_run",
  "draft_canceled",
  "not_completed",
  "run_complete",
]);

export default function StrategyConfirmationCard({ confirmation, onAction, onDirectEdit }: StrategyConfirmationCardProps) {
  const { t, i18n } = useTranslation();
  const displayState = confirmationDisplayState(confirmation, t);
  const viewModel = confirmationCardViewModel(confirmation, t, i18n.language);
  const canShowActions =
    (confirmation.confirmation_state === "active" || !confirmation.confirmation_state) &&
    confirmationStatusAllowsActions(displayState.status);
  const activeActions = canShowActions ? confirmation.actions ?? [] : [];
  const canDirectEdit =
    canShowActions &&
    onDirectEdit !== undefined &&
    (confirmation.capabilities?.direct_edits?.length ?? 0) > 0;
  const StatusIcon = displayState.icon;
  // Motion is the feedback for a deliberate add: freshly added chips animate
  // in, and nothing narrates the action back to the user.
  const addedSymbols = new Set(
    (confirmation.assets_adjustment?.added ?? []).map((item) => item.symbol),
  );
  // Consequences the user did not choose disclose inline where they land:
  // a basket change that clamps the shared history window notes it next to
  // the period value, never in a banner.
  const periodChange = confirmation.assets_adjustment?.period_change ?? null;
  const periodChangeNote = periodChange
    ? t("chat.confirmation.period_adjustment", {
        defaultValue:
          "I adjusted the test period to {{period}} because every asset and the benchmark need a shared data window.",
        period:
          compactDateRangeDisplay(periodChange.to, i18n.language) ??
          `${periodChange.to.start} → ${periodChange.to.end}`,
      })
    : null;

  return (
    <section className="argus-card-reveal argus-confirmation-reveal w-full overflow-hidden rounded-[20px] border border-[#c9c9cd] bg-white text-[#191c1f] dark:border-white/12 dark:bg-[#1d2023] dark:text-white">
      <div className="flex items-start justify-between gap-4 px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
            {viewModel.assetSymbols.length > 0 && (
              <AssetSymbols
                symbols={viewModel.assetSymbols}
                animatedSymbols={addedSymbols}
              />
            )}
            {viewModel.strategyLabel && (
              <h3 className="font-display text-[18px] font-medium leading-tight tracking-[-0.18px]">
                {viewModel.strategyLabel}
              </h3>
            )}
          </div>
        </div>
        <span
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium tracking-tight ${artifactStatusToneClassName(displayState.tone)}`}
          data-confirmation-status={displayState.status}
        >
          <StatusIcon
            aria-hidden="true"
            className={`h-3.5 w-3.5 ${displayState.isSpinning ? "animate-spin" : ""}`}
          />
          {displayState.statusLabel}
        </span>
      </div>

      {(viewModel.summaryRows.length > 0 || viewModel.detailRows.length > 0) && (
        <div className="border-t border-[#c9c9cd]/30 px-4 py-4 dark:border-white/[0.06] sm:px-5">
          {viewModel.summaryRows.length > 0 && (
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {viewModel.summaryRows.map((row) => (
                <div key={row.label} className="min-w-0">
                  <dt className="text-[11px] font-medium uppercase tracking-[0.08em] text-[#8d969e]">
                    {row.label}
                  </dt>
                  <ConfirmationValue row={row} variant="summary" />
                  {row.key === "period" && periodChangeNote ? (
                    <p
                      data-testid="confirmation-period-change-note"
                      className="mt-1 text-[12px] leading-snug text-[#8d969e]"
                    >
                      {periodChangeNote}
                    </p>
                  ) : null}
                </div>
              ))}
            </dl>
          )}

          {viewModel.retestPeriod && (
            <RetestPeriodDisclosure
              period={viewModel.retestPeriod}
              language={i18n.language}
              t={t}
            />
          )}

          {viewModel.detailRows.length > 0 && (
            <dl className={`${viewModel.summaryRows.length > 0 ? "mt-4 border-t border-[#c9c9cd]/22 pt-4 dark:border-white/[0.04]" : ""} grid grid-cols-1 gap-3 sm:grid-cols-2`}>
              {viewModel.detailRows.map((row) => (
                <div key={row.label} className="min-w-0">
                  <dt className="text-[12px] text-[#8d969e]">{row.label}</dt>
                  <ConfirmationValue row={row} variant="detail" />
                </div>
              ))}
            </dl>
          )}
        </div>
      )}

      {viewModel.assumptions.length > 0 && (
        <div className="border-t border-[#c9c9cd]/22 px-4 py-3 text-[12px] leading-snug tracking-[0.16px] text-[#8d969e] dark:border-white/[0.04] sm:px-5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {viewModel.assumptions.map((text) => (
              <span key={text} className="flex min-w-0 items-start gap-1.5 whitespace-normal break-words">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[#8d969e]/45" />
                {text}
              </span>
            ))}
          </div>
        </div>
      )}

      {canDirectEdit && (
        // The editing strip: one line of Edit capital, Edit dates, Edit
        // costs between its own hairlines; the open editor's drawer expands
        // in flow directly under the pill row, pushing the actions down.
        <div className="border-t border-[#c9c9cd]/22 px-4 py-3 text-[12px] leading-snug tracking-[0.16px] text-[#8d969e] dark:border-white/[0.04] sm:px-5">
          <ConfirmationDirectEditControls
            confirmation={confirmation}
            onDirectEdit={onDirectEdit}
            t={t}
          />
        </div>
      )}

      {activeActions.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t border-[#c9c9cd]/30 px-4 py-3.5 dark:border-white/[0.06] sm:px-5">
          {activeActions.map((action) => (
            <button
              key={action.id ?? action.type ?? action.label}
              type="button"
              onClick={() => onAction?.(action)}
              className={actionClassName}
            >
              <ConfirmationActionIcon action={action} />
              {displayConfirmationActionLabel(action, t)}
            </button>
          ))}
        </div>
      )}

    </section>
  );
}

function ConfirmationValue({
  row,
  variant,
}: {
  row: ConfirmationCardRow;
  variant: "summary" | "detail";
}) {
  if (row.key === "period") {
    const period = splitPeriodDisplay(row.value);
    return (
      <dd className={variant === "summary"
        ? "mt-1 text-[17px] font-semibold leading-snug tracking-tight text-[#191c1f] dark:text-white"
        : "mt-0.5 text-[14px] font-medium leading-[1.45] text-[#191c1f] dark:text-white/76"
      } title={row.fullValue}>
        <span className="block whitespace-normal break-words">{period.label}</span>
        {period.dates && (
          <span className="mt-0.5 block text-[13px] font-medium leading-snug text-[#505a63] dark:text-[#8d969e]">
            {period.dates}
          </span>
        )}
      </dd>
    );
  }
  return (
    <dd className={variant === "summary"
      ? "mt-1 whitespace-normal break-words text-[17px] font-semibold leading-snug tracking-tight text-[#191c1f] dark:text-white"
      : "mt-0.5 whitespace-normal break-words text-[14px] font-medium leading-[1.45] text-[#191c1f] dark:text-white/76"
    }>
      {row.value}
    </dd>
  );
}

function confirmationDisplayState(confirmation: StrategyConfirmationPayload, t: TFunction) {
  const status = confirmationStatusFromPayload(confirmation);
  const statusLabel = t(
    confirmationStatusLabelKey(status),
    confirmation.statusLabel?.trim() || confirmationStatusLabel(status),
  );
  const statusIcon = confirmationStatusIcon(status);
  const tone: ArtifactStatusTone =
    confirmation.confirmation_state === "active" &&
    !TERMINAL_CONFIRMATION_STATUSES.has(status)
      ? "info"
      : artifactLifecycleTone(status);
  return {
    ...statusIcon,
    status,
    statusLabel,
    tone,
  };
}

function confirmationStatusIcon(
  status: StrategyConfirmationStatus,
): ConfirmationStatusIconState {
  return CONFIRMATION_STATUS_ICON_STATE[status];
}

function RetestPeriodDisclosure({
  period,
  language,
  t,
}: {
  period: RetestPeriod;
  language: string;
  t: TFunction;
}) {
  const duration = retestEffectiveDurationLabel(period.duration, t, language);
  return (
    <div
      className="mt-4 border-t border-[#c9c9cd]/22 pt-4 dark:border-white/[0.04]"
      data-retest-period="extended"
    >
      <p className="whitespace-normal break-words text-[14px] font-medium leading-[1.45] text-[#191c1f] dark:text-white/76">
        {retestPeriodTransformationLabel(period, language)}
      </p>
      <p className="mt-1 text-[12px] leading-snug text-[#8d969e]">
        {t("chat.retest.updated_duration", {
          defaultValue: "Updated span: {{duration}}",
          duration,
        })}
      </p>
    </div>
  );
}

function AssetSymbols({
  symbols,
  animatedSymbols,
}: {
  symbols: string[];
  animatedSymbols?: Set<string>;
}) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {symbols.map((symbol) => (
        <span
          key={symbol}
          data-testid={
            animatedSymbols?.has(symbol) ? "confirmation-added-chip" : undefined
          }
          className={animatedSymbols?.has(symbol) ? "argus-chip-appear" : undefined}
        >
          <EntityToken kind="asset" surface="card">
            {symbol}
          </EntityToken>
        </span>
      ))}
    </span>
  );
}

function displayConfirmationActionLabel(action: ChatActionOption, t: TFunction) {
  const key = confirmationActionLabelKey(action);
  return key ? t(key, action.label) : action.label;
}

function ConfirmationActionIcon({ action }: { action: ChatActionOption }) {
  if (action.type === "run_backtest") {
    return <Play className="h-3.5 w-3.5" />;
  }
  if (action.type === "change_dates") {
    return <CalendarDays className="h-3.5 w-3.5" />;
  }
  if (action.type === "change_asset") {
    return <Search className="h-3.5 w-3.5" />;
  }
  if (action.type === "adjust_assumptions") {
    return <SlidersHorizontal className="h-3.5 w-3.5" />;
  }
  if (action.type === "cancel_confirmation") {
    return <CircleSlash2 className="h-3.5 w-3.5" />;
  }
  return <PencilLine className="h-3.5 w-3.5" />;
}
