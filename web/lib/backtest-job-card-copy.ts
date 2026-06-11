import type { BacktestJob } from "./argus-api";
import type { ArtifactStatusTone } from "./artifact-status-tones";

export type BacktestJobCardTone = ArtifactStatusTone;
export type BacktestJobCardIcon =
  | "alert"
  | "check"
  | "clock"
  | "loader"
  | "x";

export type BacktestJobCardCopy = {
  bodyFallback: string;
  bodyKey: string;
  detailFallback: string;
  detailKey: string;
  icon: BacktestJobCardIcon;
  statusLabelFallback: string;
  statusLabelKey: string;
  titleFallback: string;
  titleKey: string;
  tone: BacktestJobCardTone;
};

type BacktestJobCardCopyOptions = {
  canRetry?: boolean;
};

export function backtestJobCardCopy(
  job: BacktestJob,
  options: BacktestJobCardCopyOptions = {},
): BacktestJobCardCopy {
  if (job.status === "failed") {
    const canShowRetryCopy = job.retryable && options.canRetry === true;
    return {
      bodyFallback: canShowRetryCopy
        ? "The run stopped before Argus could save a result. You can retry this idea from the latest confirmation."
        : "The run stopped before Argus could save a result. Adjust the idea if needed and try again.",
      bodyKey: canShowRetryCopy
        ? "chat.backtest_job.failed_retryable_body"
        : "chat.backtest_job.failed_body",
      detailFallback: "The conversation is saved, and this status will stay here.",
      detailKey: "chat.backtest_job.failed_detail",
      icon: "alert",
      statusLabelFallback: "Could not run",
      statusLabelKey: "chat.backtest_job.failed_status",
      titleFallback: "Backtest could not finish",
      titleKey: "chat.backtest_job.failed_title",
      tone: "danger",
    };
  }
  if (job.status === "canceled" || job.status === "expired") {
    return {
      bodyFallback: "This run did not complete. Start a fresh backtest when you are ready.",
      bodyKey: "chat.backtest_job.expired_body",
      detailFallback: "Argus will not keep showing a running state for this job.",
      detailKey: "chat.backtest_job.expired_detail",
      icon: "x",
      statusLabelFallback: "Not completed",
      statusLabelKey: "chat.backtest_job.expired_status",
      titleFallback: "Backtest not completed",
      titleKey: "chat.backtest_job.expired_title",
      tone: "neutral",
    };
  }
  if (job.status === "succeeded") {
    return {
      bodyFallback: "The result is ready. Argus is loading the saved card.",
      bodyKey: "chat.backtest_job.succeeded_body",
      detailFallback: "The completed result will replace this progress card.",
      detailKey: "chat.backtest_job.succeeded_detail",
      icon: "check",
      statusLabelFallback: "Result ready",
      statusLabelKey: "chat.backtest_job.succeeded_status",
      titleFallback: "Backtest finished",
      titleKey: "chat.backtest_job.succeeded_title",
      tone: "neutral",
    };
  }
  if (job.status === "running") {
    return {
      bodyFallback: "Argus is calculating the result in the background.",
      bodyKey: "chat.backtest_job.running_body",
      detailFallback: "You can leave this chat and come back; progress is saved.",
      detailKey: "chat.backtest_job.running_detail",
      icon: "loader",
      statusLabelFallback: "Running",
      statusLabelKey: "chat.backtest_job.running_status",
      titleFallback: "Backtest running",
      titleKey: "chat.backtest_job.running_title",
      tone: "info",
    };
  }
  return {
    bodyFallback: "Argus has the request and will start shortly.",
    bodyKey: "chat.backtest_job.queued_body",
    detailFallback: "You can leave this chat and come back; progress is saved.",
    detailKey: "chat.backtest_job.queued_detail",
    icon: "clock",
    statusLabelFallback: "Queued",
    statusLabelKey: "chat.backtest_job.queued_status",
    titleFallback: "Backtest queued",
    titleKey: "chat.backtest_job.queued_title",
    tone: "info",
  };
}
