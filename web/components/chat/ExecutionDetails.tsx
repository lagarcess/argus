import { ChevronDown } from "lucide-react";
import { useId, type ReactNode } from "react";

/**
 * The one inline-disclosure idiom for cards: a modest pill with a chevron
 * that drops a panel in place without taking attention off the card. The
 * result card uses the read-only shape ("View details", range details); the
 * confirmation card's edit affordances use the editable shape. One
 * component, two shapes; never fork the vocabulary.
 *
 * Both shapes expand in normal flow, exactly like a native `<details>`
 * element: the trigger line stays where it is and the open panel appears
 * below it, pushing what follows down. No `display: contents`, no
 * order/basis tricks, no overlays; the card never disappears behind its own
 * drawer.
 *
 * Read-only shape: pass `details` rows; renders an uncontrolled `<details>`.
 *
 * Editable shape: pass `triggers` with `openKey`/`onToggle` and the open
 * panel as `children`; renders a pill row and, when a trigger is open, the
 * panel directly under the row. The caller owns single-open behaviour. A
 * panel with more fields simply expands taller; the layout never changes.
 */

const triggerPillClassName =
  "inline-flex cursor-pointer select-none items-center gap-1 rounded-full border border-black/8 bg-black/[0.02] px-2.5 py-1 font-medium text-[#505a63] transition-colors hover:border-black/14 hover:bg-black/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/14 dark:border-white/8 dark:bg-white/[0.03] dark:text-[#8d969e] dark:hover:border-white/14 dark:hover:bg-white/[0.06] dark:focus-visible:ring-white/14";

const panelClassName =
  "mt-2 rounded-[12px] bg-black/[0.018] px-3 py-2.5 dark:bg-white/[0.025]";

export type ExecutionDetailsTrigger = {
  key: string;
  label: string;
  icon?: ReactNode;
  testId?: string;
};

type ExecutionDetailsProps = {
  triggerLabel?: string;
  details?: { label: string; value: string }[];
  triggers?: ExecutionDetailsTrigger[];
  openKey?: string | null;
  onToggle?: (key: string) => void;
  children?: ReactNode;
  panelTestId?: string;
};

export function ExecutionDetails({
  triggerLabel,
  details,
  triggers,
  openKey,
  onToggle,
  children,
  panelTestId,
}: ExecutionDetailsProps) {
  const panelId = useId();

  if (triggers !== undefined) {
    const isOpen = openKey != null && children !== undefined;
    return (
      <div className="text-[11px] leading-snug tracking-[0.16px]">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {triggers.map((trigger) => (
            <button
              key={trigger.key}
              type="button"
              onClick={() => onToggle?.(trigger.key)}
              aria-expanded={openKey === trigger.key}
              aria-controls={openKey === trigger.key ? panelId : undefined}
              data-testid={trigger.testId}
              className={triggerPillClassName}
            >
              {trigger.icon}
              {trigger.label}
              <ChevronDown
                aria-hidden="true"
                className={`h-3 w-3 transition-transform ${
                  openKey === trigger.key ? "rotate-180" : ""
                }`}
              />
            </button>
          ))}
        </div>
        {isOpen && (
          <div id={panelId} data-testid={panelTestId} className={panelClassName}>
            {children}
          </div>
        )}
      </div>
    );
  }

  if (!details || details.length === 0) return null;

  return (
    <details className="group mt-3 rounded-[14px] text-[11px] leading-snug tracking-[0.16px] text-[#8d969e]">
      <summary className={`${triggerPillClassName} marker:text-transparent`}>
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
