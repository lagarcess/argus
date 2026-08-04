import type { ReactNode } from "react";
import { MessageSquareWarning } from "lucide-react";
import {
  quietNoticeBodyClass,
  quietNoticeContainerClass,
  quietNoticeIconClass,
} from "@/lib/failure-treatment";

type FailureNoticeProps = {
  children: ReactNode;
  className?: string;
  testId?: string;
};

/**
 * Quiet failure notice: a bordered statement for non-retryable failures.
 * The amber retryable treatment lives in ChatMessage (issue #313 lane owns
 * its reconciliation); consolidate both here only after that lane lands.
 */
export default function FailureNotice({
  children,
  className,
  testId,
}: FailureNoticeProps) {
  return (
    <div
      role="status"
      data-testid={testId}
      className={`${quietNoticeContainerClass}${className ? ` ${className}` : ""}`}
    >
      <MessageSquareWarning className={quietNoticeIconClass} aria-hidden="true" />
      <div className={quietNoticeBodyClass}>{children}</div>
    </div>
  );
}
