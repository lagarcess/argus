import {
  CalendarDays,
  CheckCircle2,
  CircleSlash2,
  Loader2,
  Pencil,
  PencilLine,
  Play,
  RefreshCw,
  Search,
  Send,
  SlidersHorizontal,
  TriangleAlert,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import {
  artifactLifecycleTone,
  artifactStatusToneClassName,
  type ArtifactStatusTone,
} from "@/lib/artifact-status-tones";
import { cadenceDisplayLabel } from "@/lib/cadence-display";
import { confirmationAssumptionDisplay } from "@/lib/confirmation-assumptions-display";
import { compactDateRangeDisplay } from "@/lib/date-range-display";
import {
  strategyDisplayLabel,
  strategyTypeFromConfirmation,
} from "@/lib/strategy-display";
import {
  type ChatActionOption,
  type StrategyConfirmationPayload,
  type StrategyConfirmationRowKey,
  type StrategyConfirmationStatus,
} from "./types";
import { splitPeriodDisplay, splitSymbolList } from "./card-formatting";
import {
  confirmationActionLabelKey,
  confirmationRowKey,
  confirmationRowLabelKey,
  confirmationStatusFromPayload,
  confirmationStatusLabel,
  confirmationStatusLabelKey,
} from "./confirmation-display";

type StrategyConfirmationCardProps = {
  confirmation: StrategyConfirmationPayload;
  onAction?: (action: ChatActionOption) => void;
};

type ConfirmationCardRow = StrategyConfirmationPayload["rows"][number] & {
  fullValue?: string;
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
  "inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.03] px-3 py-1.5 text-[12px] font-medium tracking-tight text-black/76 transition-colors hover:border-black/18 hover:bg-black/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 active:scale-[0.98] dark:border-white/10 dark:bg-white/[0.04] dark:text-white/76 dark:hover:border-white/18 dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/22";

export default function StrategyConfirmationCard({ confirmation, onAction }: StrategyConfirmationCardProps) {
  const { t, i18n } = useTranslation();
  const displayState = confirmationDisplayState(confirmation, t);
  const viewModel = confirmationCardViewModel(confirmation, t, i18n.language);
  const activeActions =
    confirmation.confirmation_state === "active" || !confirmation.confirmation_state
      ? confirmation.actions ?? []
      : [];
  const StatusIcon = displayState.icon;

  return (
    <section className="argus-card-reveal argus-confirmation-reveal w-full overflow-hidden rounded-[20px] border border-[#c9c9cd] bg-white text-[#191c1f] dark:border-white/12 dark:bg-[#1d2023] dark:text-white">
      <div className="flex items-start justify-between gap-4 px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
            {viewModel.assetSymbols.length > 0 && (
              <AssetSymbols symbols={viewModel.assetSymbols} />
            )}
            <h3 className="font-display text-[18px] font-medium leading-tight tracking-[-0.18px]">
              {viewModel.strategyLabel}
            </h3>
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
                    {displayConfirmationRowLabel(row, t)}
                  </dt>
                  <ConfirmationValue row={row} variant="summary" />
                </div>
              ))}
            </dl>
          )}

          {viewModel.detailRows.length > 0 && (
            <dl className={`${viewModel.summaryRows.length > 0 ? "mt-4 border-t border-[#c9c9cd]/22 pt-4 dark:border-white/[0.04]" : ""} grid grid-cols-1 gap-3 sm:grid-cols-2`}>
              {viewModel.detailRows.map((row) => (
                <div key={row.label} className="min-w-0">
                  <dt className="text-[12px] text-[#8d969e]">
                    {displayConfirmationRowLabel(row, t)}
                  </dt>
                  <ConfirmationValue row={row} variant="detail" />
                </div>
              ))}
            </dl>
          )}
        </div>
      )}

      {viewModel.assumptions.length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-1 border-t border-[#c9c9cd]/22 px-4 py-3 text-[12px] leading-snug tracking-[0.16px] text-[#8d969e] dark:border-white/[0.04] sm:px-5">
          {viewModel.assumptions.map((text) => (
            <span key={text} className="flex min-w-0 items-start gap-1.5 whitespace-normal break-words">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[#8d969e]/45" />
              {text}
            </span>
          ))}
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
  if (confirmationRowKey(row) === "period") {
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
    confirmation.confirmation_state === "active" && status === "editing"
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

function confirmationCardViewModel(
  confirmation: StrategyConfirmationPayload,
  t: TFunction,
  language: string,
) {
  const rows = confirmation.rows.map((row) => ({
    key: confirmationRowKey(row),
    row: displayConfirmationRowValue(row, t),
  }));
  const assetRow = rowForKey(rows, "assets");
  const strategyRow = rowForKey(rows, "strategy");
  const periodRow = rowForKey(rows, "period");
  const startingCapitalRow = rowForKey(rows, "starting_capital");
  const contributionRow = rowForKey(rows, "contribution");
  const assetSymbols = splitSymbolList(assetRow?.value ?? "");
  const primaryCapitalRow = startingCapitalRow ?? contributionRow;
  const compactPeriod = compactDateRangeDisplay(confirmation.date_range, language);
  const displayPeriodRow =
    periodRow && compactPeriod
      ? {
          ...periodRow,
          value: compactPeriod,
          fullValue: confirmation.date_range?.display ?? periodRow.value,
        }
      : periodRow;
  const summaryRows = [primaryCapitalRow, displayPeriodRow].filter(isConfirmationRow);
  const promotedKeys = new Set<StrategyConfirmationRowKey>([
    "assets",
    "strategy",
    ...summaryRows
      .map((row) => confirmationRowKey(row))
      .filter(isConfirmationRowKey),
  ]);
  if (primaryCapitalRow === contributionRow) {
    promotedKeys.add("contribution");
  }
  const summaryRowSet = new Set(summaryRows);
  const detailRows = rows
    .filter(
      ({ key, row }) =>
        !summaryRowSet.has(row) && (key === null || !promotedKeys.has(key)),
    )
    .map(({ row }) => row);
  const promotedValues = summaryRows.map((row) => row.value);
  const localizedStrategyLabel = strategyDisplayLabel(
    strategyTypeFromConfirmation(confirmation),
    t,
    strategyRow?.value,
  );

  return {
    assetSymbols,
    strategyLabel:
      localizedStrategyLabel ??
      confirmationAssetTitle(assetRow, confirmation.title, t),
    summaryRows,
    detailRows,
    assumptions: confirmationAssumptionDisplay({
      assetClass: confirmation.asset_class,
      displayFacts: confirmation.display_facts,
      fallbackAssumptions: confirmation.assumptions ?? [],
      locale: language,
      promotedValues,
      t,
    }),
  };
}

function displayConfirmationRowValue(
  row: StrategyConfirmationPayload["rows"][number],
  t: TFunction,
): StrategyConfirmationPayload["rows"][number] {
  if (confirmationRowKey(row) !== "cadence") {
    return row;
  }
  const displayValue = cadenceDisplayLabel(row.value, t);
  return displayValue && displayValue !== row.value
    ? { ...row, value: displayValue }
    : row;
}

function isConfirmationRow(
  row: StrategyConfirmationPayload["rows"][number] | undefined,
): row is StrategyConfirmationPayload["rows"][number] {
  return Boolean(row);
}

function isConfirmationRowKey(
  key: StrategyConfirmationRowKey | null,
): key is StrategyConfirmationRowKey {
  return key !== null;
}

function rowForKey(
  rows: Array<{
    key: StrategyConfirmationRowKey | null;
    row: StrategyConfirmationPayload["rows"][number];
  }>,
  key: StrategyConfirmationRowKey,
) {
  return rows.find((entry) => entry.key === key)?.row;
}

function confirmationAssetTitle(
  assetRow: StrategyConfirmationPayload["rows"][number] | undefined,
  fallbackTitle: string,
  t: TFunction,
) {
  const symbols = splitSymbolList(assetRow?.value ?? "");
  if (symbols.length === 1) {
    return symbols[0];
  }
  if (symbols.length === 2) {
    return symbols.join(" + ");
  }
  if (symbols.length > 2) {
    return t("chat.confirmation.asset_count", "{{count}} assets", {
      count: symbols.length,
    });
  }
  return fallbackTitle.trim() || t("chat.confirmation.selected_asset", "Selected asset");
}

function AssetSymbols({ symbols }: { symbols: string[] }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {symbols.map((symbol) => (
        <span
          key={symbol}
          className="rounded-[7px] border border-[#c9c9cd]/65 px-2 py-1 text-[12px] font-medium leading-none tracking-[0.16px] text-[#505a63] dark:border-white/14 dark:text-[#8d969e]"
        >
          {symbol}
        </span>
      ))}
    </span>
  );
}

function displayConfirmationRowLabel(
  row: StrategyConfirmationPayload["rows"][number],
  t: TFunction,
) {
  const key = confirmationRowLabelKey(row);
  return key ? t(key, row.label) : row.label;
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
