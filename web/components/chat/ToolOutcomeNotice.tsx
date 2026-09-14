import { MessageSquareWarning } from "lucide-react";
import type { ToolOutcomeTreatment } from "@/lib/tool-outcome-treatment";
import type { ToolScalar } from "@/lib/tool-result-card";

/**
 * One notice for every unsuccessful calculation outcome, styled by the
 * treatment owner: amber with a retry for an outage, quiet naming the input
 * otherwise, and the backend's typed repair as a tap when it computed one.
 */
export default function ToolOutcomeNotice({ treatment, repairLabel, retryLabel, onRepair, onRetry, disabled = false, testId }: {
  treatment: ToolOutcomeTreatment;
  repairLabel?: string | null;
  retryLabel?: string | null;
  onRepair?: (changes: Record<string, ToolScalar>) => void;
  onRetry?: () => void;
  disabled?: boolean;
  testId?: string;
}) {
  const repair = treatment.repair;
  return (
    <div role="status" data-testid={testId} data-tool-outcome-tone={treatment.tone} data-tool-outcome-code={treatment.code} className={treatment.classes.container}>
      <MessageSquareWarning className={treatment.classes.icon} aria-hidden="true" />
      <div className={treatment.classes.body}>{treatment.message}</div>
      {repair && onRepair && repairLabel ? (
        <button type="button" disabled={disabled} data-tool-repair={repair.kind} onClick={() => onRepair(repair.changes)}
          className="max-w-full shrink-0 self-center rounded-full border border-black/15 px-3 py-1.5 text-[13px] font-medium text-black/75 transition-colors hover:bg-black/[0.04] disabled:opacity-50 dark:border-white/20 dark:text-white/75 dark:hover:bg-white/10">
          {repairLabel}
        </button>
      ) : null}
      {treatment.tone === "retryable" && onRetry && retryLabel && treatment.classes.retryPill ? (
        <button type="button" disabled={disabled} data-tool-retry="true" onClick={onRetry} className={treatment.classes.retryPill}>
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}
