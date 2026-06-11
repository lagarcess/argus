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
import { useTranslation } from "react-i18next";
import {
  artifactLifecycleTone,
  artifactStatusToneClassName,
  type ArtifactStatusTone,
} from "@/lib/artifact-status-tones";
import { type ChatActionOption, type StrategyConfirmationPayload } from "./types";
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
  const primaryRows = confirmation.rows.slice(0, 3);
  const detailRows = confirmation.rows.slice(3);
  const displayState = confirmationDisplayState(confirmation, t);
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
            {confirmation.title}
          </p>
          <p className="mt-1.5 text-[13px] leading-snug tracking-[0.16px] text-[#505a63] dark:text-[#8d969e]">
            {confirmation.summary}
          </p>
        </div>
        <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium tracking-tight ${artifactStatusToneClassName(displayState.tone)}`}>
          <StatusIcon className={`h-3.5 w-3.5 ${displayState.isSpinning ? "animate-spin" : ""}`} />
          {displayState.statusLabel}
        </span>
      </div>

      <div className="border-t border-[#c9c9cd]/30 px-4 py-4 dark:border-white/[0.06] sm:px-5">
        <dl className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
          {primaryRows.map((row) => (
            <div key={row.label} className="min-w-0">
              <dt className="text-[11px] font-medium uppercase tracking-[0.08em] text-[#8d969e]">
                {displayConfirmationRowLabel(row, t)}
              </dt>
              <ConfirmationValue row={row} t={t} />
            </div>
          ))}
        </dl>

        {detailRows.length > 0 && (
          <dl className="mt-4 grid grid-cols-1 gap-3 border-t border-[#c9c9cd]/22 pt-4 dark:border-white/[0.04] sm:grid-cols-2">
            {detailRows.map((row) => (
              <div key={row.label} className="min-w-0">
                <dt className="text-[12px] text-[#8d969e]">
                  {displayConfirmationRowLabel(row, t)}
                </dt>
                <dd className="mt-0.5 whitespace-normal break-words text-[14px] font-medium leading-[1.45] text-[#191c1f] dark:text-white/76">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {confirmation.assumptions && confirmation.assumptions.length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-1 border-t border-[#c9c9cd]/22 px-4 py-3 text-[12px] leading-snug tracking-[0.16px] text-[#8d969e] dark:border-white/[0.04] sm:px-5">
          {confirmation.assumptions.map((text) => (
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
  t,
}: {
  row: StrategyConfirmationPayload["rows"][number];
  t: any;
}) {
  if (confirmationRowKey(row) === "assets") {
    return <AssetList symbols={splitSymbolList(row.value)} t={t} />;
  }
  if (confirmationRowKey(row) === "period") {
    const period = splitPeriodDisplay(row.value);
    return (
      <dd className="mt-1 text-[15px] font-semibold leading-snug tracking-tight text-[#191c1f] dark:text-white">
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
    <dd className="mt-1 whitespace-normal break-words text-[15px] font-semibold leading-snug tracking-tight text-[#191c1f] dark:text-white">
      {row.value}
    </dd>
  );
}

function AssetList({ symbols, t }: { symbols: string[]; t: any }) {
  if (symbols.length === 0) {
    return (
      <dd className="mt-1 text-[15px] font-semibold leading-snug tracking-tight text-[#191c1f] dark:text-white">
        {t("chat.confirmation.selected_asset", "Selected asset")}
      </dd>
    );
  }
  return (
    <dd className="mt-1 flex flex-wrap gap-x-2 gap-y-1">
      {symbols.map((symbol) => (
        <span
          key={symbol}
          className="rounded-[7px] border border-[#c9c9cd]/65 px-2 py-1 text-[12px] font-medium leading-none tracking-[0.16px] text-[#505a63] dark:border-white/14 dark:text-[#8d969e]"
        >
          {symbol}
        </span>
      ))}
    </dd>
  );
}

function confirmationDisplayState(confirmation: StrategyConfirmationPayload, t: any) {
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

function displayConfirmationRowLabel(
  row: StrategyConfirmationPayload["rows"][number],
  t: any,
) {
  const key = confirmationRowLabelKey(row);
  return key ? t(key, row.label) : row.label;
}

function displayConfirmationActionLabel(action: ChatActionOption, t: any) {
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
