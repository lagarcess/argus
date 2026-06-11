export type ArtifactStatusTone = "info" | "neutral" | "danger" | "success";

const artifactStatusToneClasses = {
  danger:
    "border-[#d66d75]/25 bg-[#d66d75]/8 text-[#96505a] dark:border-[#d66d75]/30 dark:bg-[#d66d75]/12 dark:text-[#e0a1a7]",
  info:
    "border-[#7da0ca]/25 bg-[#7da0ca]/8 text-[#4f6f95] dark:border-[#7da0ca]/30 dark:bg-[#7da0ca]/12 dark:text-[#a7bdd7]",
  neutral:
    "border-black/10 bg-black/[0.03] text-black/70 dark:border-white/10 dark:bg-white/[0.04] dark:text-white/70",
  success:
    "border-[#70a38d]/25 bg-[#70a38d]/10 text-[#4f806d] dark:border-[#70a38d]/30 dark:bg-[#70a38d]/12 dark:text-[#9bc6b4]",
} satisfies Record<ArtifactStatusTone, string>;

const infoLifecycleStatuses = new Set([
  "queued",
  "ready_to_run",
  "request_sent",
  "running",
]);

const neutralLifecycleStatuses = new Set([
  "canceled",
  "draft_canceled",
  "expired",
  "not_completed",
  "result_ready",
  "run_complete",
  "simulation_complete",
  "succeeded",
]);

const dangerLifecycleStatuses = new Set(["could_not_run", "failed"]);

export function artifactStatusToneClassName(tone: ArtifactStatusTone): string {
  return artifactStatusToneClasses[tone];
}

export function artifactLifecycleTone(status: string): ArtifactStatusTone {
  if (infoLifecycleStatuses.has(status)) return "info";
  if (neutralLifecycleStatuses.has(status)) return "neutral";
  if (dangerLifecycleStatuses.has(status)) return "danger";
  if (status === "saved" || status === "saving") return "success";
  return "neutral";
}
