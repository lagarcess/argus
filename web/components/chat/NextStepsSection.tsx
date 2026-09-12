"use client";

import type { TFunction } from "i18next";

import NextMoveRow, {
  NextMoveDetail,
  NextMoveSeparator,
  NextMoveTicker,
  NextMoveTitle,
} from "./NextMoveRow";
import type { ChatActionOption } from "./types";
import {
  nextExperimentAction,
  nextExperimentReasonText,
} from "@/lib/chat-next-experiments";
import { nextStepQuestionAction, type NextStep } from "@/lib/chat-next-steps";

type NextStepsSectionProps = {
  steps: NextStep[];
  disabled: boolean;
  isBelowTablet: boolean;
  locale: string;
  onAction?: (action: ChatActionOption) => void;
  sourceRunId?: string;
  t: TFunction;
};

/**
 * The one next-move list under a message, in the order the backend sent it.
 * A test row runs its typed Try next action; a question row asks its question.
 */
export default function NextStepsSection({
  steps,
  disabled,
  isBelowTablet,
  locale,
  onAction,
  sourceRunId,
  t,
}: NextStepsSectionProps) {
  if (steps.length === 0) {
    return null;
  }
  const sectionLabel = t("chat.next_experiments.section", "Try next");
  const firstTestIndex = steps.findIndex((step) => step.type === "test");
  return (
    <section
      aria-label={sectionLabel}
      className="mt-5 flex w-full max-w-[min(100%,660px)] flex-col"
    >
      <div className="argus-result-section-label">{sectionLabel}</div>
      <div className="flex w-full flex-col divide-y divide-black/8 dark:divide-white/8">
        {steps.map((step, stepIndex) => {
          if (step.type === "question") {
            return (
              <NextMoveRow
                key={`question:${step.text}`}
                ariaLabel={step.text}
                disabled={disabled}
                onClick={() => onAction?.(nextStepQuestionAction(step.text))}
              >
                <NextMoveTitle>{step.text}</NextMoveTitle>
              </NextMoveRow>
            );
          }
          const { row } = step;
          const rowLabel = t(row.labelKey, row.label);
          // Narrow screens read the backend's short form; the clamp
          // below is only a safety net, never a single-line ellipsis.
          const narrowLabel =
            isBelowTablet && row.labelShortKey
              ? t(row.labelShortKey, row.labelShort ?? row.label)
              : rowLabel;
          // One result-level reason; captioning every row repeats it.
          const whyText =
            stepIndex === firstTestIndex
              ? nextExperimentReasonText(row.why, t, locale)
              : "";
          return (
            <NextMoveRow
              key={`test:${row.kind}`}
              ariaLabel={rowLabel}
              disabled={disabled}
              onClick={() =>
                onAction?.(nextExperimentAction(row, rowLabel, sourceRunId))
              }
            >
              <NextMoveTitle>
                {row.labelParts
                  ? row.labelParts.map((part, partIndex) =>
                      part.type === "ticker" ? (
                        <span key={partIndex}>
                          {" "}
                          <NextMoveTicker>{part.value}</NextMoveTicker>
                        </span>
                      ) : (
                        <span key={partIndex}>{part.value}</span>
                      ),
                    )
                  : narrowLabel}
              </NextMoveTitle>
              {row.detail ? (
                <>
                  <NextMoveSeparator>·</NextMoveSeparator>
                  <NextMoveDetail>{row.detail}</NextMoveDetail>
                </>
              ) : null}
              {whyText ? (
                <>
                  <NextMoveSeparator>·</NextMoveSeparator>
                  <NextMoveDetail>{whyText}</NextMoveDetail>
                </>
              ) : null}
            </NextMoveRow>
          );
        })}
      </div>
    </section>
  );
}
