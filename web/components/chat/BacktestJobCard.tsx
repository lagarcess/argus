import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  XCircle,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { BacktestJob } from "@/lib/argus-api";
import { artifactStatusToneClassName } from "@/lib/artifact-status-tones";
import {
  backtestJobCardCopy,
  type BacktestJobCardIcon,
} from "@/lib/backtest-job-card-copy";

type BacktestJobCardProps = {
  job: BacktestJob;
  canRetry?: boolean;
};

const statusIcons = {
  alert: AlertTriangle,
  check: CheckCircle2,
  clock: Clock3,
  loader: Loader2,
  x: XCircle,
} satisfies Record<BacktestJobCardIcon, typeof AlertTriangle>;

export default function BacktestJobCard({
  job,
  canRetry = false,
}: BacktestJobCardProps) {
  const { t } = useTranslation();
  const copy = backtestJobCardCopy(job, { canRetry });
  const StatusIcon = statusIcons[copy.icon];
  const title = t(copy.titleKey, copy.titleFallback);
  const body = t(copy.bodyKey, copy.bodyFallback);
  const detail = t(copy.detailKey, copy.detailFallback);
  const statusLabel = t(copy.statusLabelKey, copy.statusLabelFallback);

  return (
    <section className="argus-card-reveal w-full overflow-hidden rounded-[20px] border border-black/12 bg-white text-[#191c1f] dark:border-white/12 dark:bg-[#1d2023] dark:text-white">
      <div className="flex items-start justify-between gap-4 px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <p className="font-display text-[18px] font-medium leading-tight tracking-[-0.18px]">
            {title}
          </p>
          <p className="mt-1.5 text-[13px] leading-snug tracking-[0.16px] text-[#505a63] dark:text-[#8d969e]">
            {body}
          </p>
        </div>
        <span
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium tracking-tight ${artifactStatusToneClassName(copy.tone)}`}
        >
          <StatusIcon
            className={`h-3.5 w-3.5 ${job.status === "running" ? "animate-spin" : ""}`}
          />
          {statusLabel}
        </span>
      </div>

      <div className="border-t border-black/8 px-4 py-3 text-[12px] leading-snug tracking-[0.16px] text-[#8d969e] dark:border-white/8 sm:px-5">
        {detail}
      </div>
    </section>
  );
}
