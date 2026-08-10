import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

/**
 * The one inline-disclosure idiom for cards: a modest pill with a chevron
 * that drops a panel in place without taking attention off the card. The
 * result card uses the read-only shape ("View details", range details); the
 * confirmation card's edit affordances use the editable shape. One
 * component, two shapes; never fork the vocabulary.
 *
 * Read-only shape: pass `details` rows and nothing else; renders a native
 * `<details>` element, uncontrolled, on its own line.
 *
 * Editable shape: pass `children` with `open`/`onToggle`; renders a
 * `display: contents` wrapper so the pill participates in the surrounding
 * flex row while the open panel wraps onto a full-width line of the same
 * strip (`order-last basis-full`). The caller owns single-open behaviour
 * and may divert `onToggle` to a sheet on small screens.
 */

const triggerPillClassName =
  "inline-flex cursor-pointer select-none items-center gap-1 rounded-full border border-black/8 bg-black/[0.02] px-2.5 py-1 font-medium text-[#505a63] transition-colors hover:border-black/14 hover:bg-black/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/14 dark:border-white/8 dark:bg-white/[0.03] dark:text-[#8d969e] dark:hover:border-white/14 dark:hover:bg-white/[0.06] dark:focus-visible:ring-white/14";

const panelClassName =
  "mt-2 rounded-[12px] bg-black/[0.018] px-3 py-2.5 dark:bg-white/[0.025]";

type ExecutionDetailsProps = {
  triggerLabel: string;
  details?: { label: string; value: string }[];
  children?: ReactNode;
  open?: boolean;
  onToggle?: () => void;
  triggerIcon?: ReactNode;
  triggerTestId?: string;
  panelTestId?: string;
};

export function ExecutionDetails({
  triggerLabel,
  details,
  children,
  open,
  onToggle,
  triggerIcon,
  triggerTestId,
  panelTestId,
}: ExecutionDetailsProps) {
  if (children !== undefined) {
    const isOpen = open === true;
    return (
      <div className="contents">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={isOpen}
          data-testid={triggerTestId}
          className={`${triggerPillClassName} text-[11px] leading-snug tracking-[0.16px]`}
        >
          {triggerIcon}
          {triggerLabel}
          <ChevronDown
            aria-hidden="true"
            className={`h-3 w-3 transition-transform ${isOpen ? "rotate-180" : ""}`}
          />
        </button>
        {isOpen && (
          <div
            data-testid={panelTestId}
            className={`order-last basis-full ${panelClassName}`}
          >
            {children}
          </div>
        )}
      </div>
    );
  }

  if (!details || details.length === 0) return null;

  return (
    <details className="group mt-3 rounded-[14px] text-[11px] leading-snug tracking-[0.16px] text-[#8d969e]">
      <summary
        className={`${triggerPillClassName} marker:text-transparent`}
      >
        {triggerLabel}
        <ChevronDown className="h-3 w-3 transition-transform group-open:rotate-180" />
      </summary>
      <dl className={`${panelClassName} grid gap-x-5 gap-y-2 sm:grid-cols-2`}>
        {details.map((detail) => (
          <div
            key={`${detail.label}-${detail.value}`}
            className="grid min-w-0 grid-cols-[96px_minmax(0,1fr)] gap-x-3"
          >
            <dt className="text-[#8d969e]">{detail.label}</dt>
            <dd className="break-words font-medium text-[#191c1f] dark:text-white/76">
              {detail.value}
            </dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
