import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  XCircle,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { BacktestJob } from "@/lib/argus-api";

type BacktestJobCardProps = {
  job: BacktestJob;
};

const toneClasses = {
  active:
    "border-[#7da0ca]/25 bg-[#7da0ca]/8 text-[#4f6f95] dark:border-[#7da0ca]/30 dark:bg-[#7da0ca]/12 dark:text-[#a7bdd7]",
  failed:
    "border-[#d66d75]/25 bg-[#d66d75]/8 text-[#96505a] dark:border-[#d66d75]/30 dark:bg-[#d66d75]/12 dark:text-[#e0a1a7]",
  neutral:
    "border-[#c2a44d]/25 bg-[#c2a44d]/8 text-[#806d2f] dark:border-[#c2a44d]/30 dark:bg-[#c2a44d]/12 dark:text-[#d9c574]",
  success:
    "border-[#70a38d]/25 bg-[#70a38d]/8 text-[#4f806d] dark:border-[#70a38d]/30 dark:bg-[#70a38d]/12 dark:text-[#9bc6b4]",
};

export default function BacktestJobCard({ job }: BacktestJobCardProps) {
  const { t } = useTranslation();
  const copy = backtestJobCopy(job, t);
  const StatusIcon = copy.icon;

  return (
    <section className="argus-card-reveal w-full overflow-hidden rounded-[20px] border border-black/12 bg-white text-[#191c1f] dark:border-white/12 dark:bg-[#1d2023] dark:text-white">
      <div className="flex items-start justify-between gap-4 px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <p className="font-display text-[18px] font-medium leading-tight tracking-[-0.18px]">
            {copy.title}
          </p>
          <p className="mt-1.5 text-[13px] leading-snug tracking-[0.16px] text-[#505a63] dark:text-[#8d969e]">
            {copy.body}
          </p>
        </div>
        <span
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium tracking-tight ${toneClasses[copy.tone]}`}
        >
          <StatusIcon
            className={`h-3.5 w-3.5 ${job.status === "running" ? "animate-spin" : ""}`}
          />
          {copy.statusLabel}
        </span>
      </div>

      <div className="border-t border-black/8 px-4 py-3 text-[12px] leading-snug tracking-[0.16px] text-[#8d969e] dark:border-white/8 sm:px-5">
        {copy.detail}
      </div>
    </section>
  );
}

function backtestJobCopy(
  job: BacktestJob,
  t: ReturnType<typeof useTranslation>["t"],
) {
  if (job.status === "failed") {
    return {
      body: job.retryable
        ? t(
            "chat.backtest_job.failed_retryable_body",
            "The run stopped before a result was saved. You can retry this idea from the latest confirmation.",
          )
        : t(
            "chat.backtest_job.failed_body",
            "The run stopped before a result was saved. Adjust the idea if needed and try again.",
          ),
      detail: t(
        "chat.backtest_job.failed_detail",
        "The conversation is saved, and this status came from the durable job record.",
      ),
      icon: AlertTriangle,
      statusLabel: t("chat.backtest_job.failed_status", "Could not run"),
      title: t("chat.backtest_job.failed_title", "Backtest could not finish"),
      tone: "failed" as const,
    };
  }
  if (job.status === "canceled" || job.status === "expired") {
    return {
      body: t(
        "chat.backtest_job.expired_body",
        "This run did not complete. Start a fresh backtest when you are ready.",
      ),
      detail: t(
        "chat.backtest_job.expired_detail",
        "Argus will not keep showing a running state for this job.",
      ),
      icon: XCircle,
      statusLabel: t("chat.backtest_job.expired_status", "Not completed"),
      title: t("chat.backtest_job.expired_title", "Backtest not completed"),
      tone: "neutral" as const,
    };
  }
  if (job.status === "succeeded") {
    return {
      body: t(
        "chat.backtest_job.succeeded_body",
        "The run finished. Argus is loading the saved result card.",
      ),
      detail: t(
        "chat.backtest_job.succeeded_detail",
        "Results are shown only after the canonical run is available.",
      ),
      icon: CheckCircle2,
      statusLabel: t("chat.backtest_job.succeeded_status", "Result ready"),
      title: t("chat.backtest_job.succeeded_title", "Backtest finished"),
      tone: "success" as const,
    };
  }
  if (job.status === "running") {
    return {
      body: t(
        "chat.backtest_job.running_body",
        "The workflow is calculating the result in the background.",
      ),
      detail: t(
        "chat.backtest_job.running_detail",
        "You can leave this chat and come back; the job state is saved.",
      ),
      icon: Loader2,
      statusLabel: t("chat.backtest_job.running_status", "Running"),
      title: t("chat.backtest_job.running_title", "Backtest running"),
      tone: "active" as const,
    };
  }
  return {
    body: t(
      "chat.backtest_job.queued_body",
      "The workflow has the request and will start shortly.",
    ),
    detail: t(
      "chat.backtest_job.queued_detail",
      "The chat stream can end while the durable job continues.",
    ),
    icon: Clock3,
    statusLabel: t("chat.backtest_job.queued_status", "Queued"),
    title: t("chat.backtest_job.queued_title", "Backtest queued"),
    tone: "active" as const,
  };
}
