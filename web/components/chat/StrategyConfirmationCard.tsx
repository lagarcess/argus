import {
  CalendarDays,
  CheckCircle2,
  CircleSlash2,
  Loader2,
  PencilLine,
  Play,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import {
  artifactLifecycleTone,
  artifactStatusToneClassName,
  type ArtifactStatusTone,
} from "@/lib/artifact-status-tones";
import {
  type ChatActionOption,
  type StrategyConfirmationPayload,
  type StrategyConfirmationRowKey,
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

const actionClassName =
  "inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.03] px-3 py-1.5 text-[12px] font-medium tracking-tight text-black/76 transition-colors hover:border-black/18 hover:bg-black/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 active:scale-[0.98] dark:border-white/10 dark:bg-white/[0.04] dark:text-white/76 dark:hover:border-white/18 dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/22";

export default function StrategyConfirmationCard({ confirmation, onAction }: StrategyConfirmationCardProps) {
  const { t } = useTranslation();
  const displayState = confirmationDisplayState(confirmation, t);
  const viewModel = confirmationCardViewModel(confirmation, t);
  const activeActions =
    confirmation.confirmation_state === "active" || !confirmation.confirmation_state
      ? confirmation.actions ?? []
      : [];
  const StatusIcon = displayState.icon;

  return (
    <section className="argus-card-reveal argus-confirmation-reveal w-full overflow-hidden rounded-[20px] border border-[#c9c9cd] bg-white text-[#191c1f] dark:border-white/12 dark:bg-[#1d2023] dark:text-white">
      <div className="flex items-start justify-between gap-4 px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <p className="font-display text-[18px] font-medium leading-tight tracking-[-0.18px]">
            {viewModel.title}
          </p>
          {viewModel.metaParts.length > 0 && (
            <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] font-medium leading-snug text-[#505a63] dark:text-[#8d969e]">
              {viewModel.metaParts.map((part, index) => (
                <span
                  key={`${part}-${index}`}
                  className={
                    index === 0
                      ? "min-w-0"
                      : "min-w-0 border-l border-[#c9c9cd]/45 pl-2 dark:border-white/12"
                  }
                >
                  {part}
                </span>
              ))}
            </div>
          )}
        </div>
        <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium tracking-tight ${artifactStatusToneClassName(displayState.tone)}`}>
          <StatusIcon className={`h-3.5 w-3.5 ${displayState.isSpinning ? "animate-spin" : ""}`} />
          {displayState.statusLabel}
        </span>
      </div>

      {(viewModel.featureRows.length > 0 || viewModel.detailRows.length > 0) && (
        <div className="border-t border-[#c9c9cd]/30 px-4 py-4 dark:border-white/[0.06] sm:px-5">
          {viewModel.featureRows.length > 0 && (
            <dl className="grid grid-cols-1 gap-4">
              {viewModel.featureRows.map((row) => (
                <div key={row.label} className="min-w-0">
                  <dt className="text-[11px] font-medium uppercase tracking-[0.08em] text-[#8d969e]">
                    {displayConfirmationRowLabel(row, t)}
                  </dt>
                  <ConfirmationValue row={row} variant="feature" />
                </div>
              ))}
            </dl>
          )}

          {viewModel.detailRows.length > 0 && (
            <dl className={`${viewModel.featureRows.length > 0 ? "mt-4 border-t border-[#c9c9cd]/22 pt-4 dark:border-white/[0.04]" : ""} grid grid-cols-1 gap-3 sm:grid-cols-2`}>
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
  row: StrategyConfirmationPayload["rows"][number];
  variant: "feature" | "detail";
}) {
  if (confirmationRowKey(row) === "period") {
    const period = splitPeriodDisplay(row.value);
    return (
      <dd className={variant === "feature"
        ? "mt-1 text-[17px] font-semibold leading-snug tracking-tight text-[#191c1f] dark:text-white"
        : "mt-0.5 text-[14px] font-medium leading-[1.45] text-[#191c1f] dark:text-white/76"
      }>
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
    <dd className={variant === "feature"
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
  if (status === "running") {
    return { icon: Loader2, isSpinning: true, statusLabel, tone: artifactLifecycleTone(status) };
  }
  if (status === "run_complete") {
    return { icon: CheckCircle2, isSpinning: false, statusLabel, tone: artifactLifecycleTone(status) };
  }
  if (status === "could_not_run") {
    return { icon: CircleSlash2, isSpinning: false, statusLabel, tone: artifactLifecycleTone(status) };
  }
  if (status === "draft_canceled") {
    return { icon: CircleSlash2, isSpinning: false, statusLabel, tone: artifactLifecycleTone(status) };
  }
  const tone: ArtifactStatusTone =
    confirmation.confirmation_state === "active" ? "info" : artifactLifecycleTone(status);
  return {
    icon: CheckCircle2,
    isSpinning: false,
    statusLabel,
    tone,
  };
}

function confirmationCardViewModel(
  confirmation: StrategyConfirmationPayload,
  t: TFunction,
) {
  const rows = confirmation.rows.map((row) => ({
    key: confirmationRowKey(row),
    row,
  }));
  const assetRow = rowForKey(rows, "assets");
  const strategyRow = rowForKey(rows, "strategy");
  const periodRow = rowForKey(rows, "period");
  const startingCapitalRow = rowForKey(rows, "starting_capital");
  const cadenceRow = rowForKey(rows, "cadence");
  const contributionRow = rowForKey(rows, "contribution");
  const promotedRows = [
    strategyRow,
    startingCapitalRow,
    contributionRow,
    cadenceRow,
  ].filter(isConfirmationRow);
  const promotedKeys = new Set<StrategyConfirmationRowKey>([
    "assets",
    ...promotedRows
      .map((row) => confirmationRowKey(row))
      .filter(isConfirmationRowKey),
  ]);
  const featureRows = periodRow
    ? [periodRow]
    : rows
        .filter(({ key }) => key === null || !promotedKeys.has(key))
        .slice(0, 1)
        .map(({ row }) => row);
  const featureRowSet = new Set(featureRows);
  const detailRows = rows
    .filter(
      ({ key, row }) =>
        !featureRowSet.has(row) && (key === null || !promotedKeys.has(key)),
    )
    .map(({ row }) => row);
  const promotedValues = promotedRows.map((row) => row.value);

  return {
    title: confirmationAssetTitle(assetRow, confirmation.title, t),
    metaParts: promotedRows.map((row) => row.value),
    featureRows,
    detailRows,
    assumptions: displayAssumptions(confirmation.assumptions ?? [], promotedValues),
  };
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

function displayAssumptions(assumptions: string[], promotedValues: string[]) {
  return assumptions.filter(
    (assumption) =>
      !promotedValues.some((value) => value.trim() && assumption.includes(value.trim())),
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
