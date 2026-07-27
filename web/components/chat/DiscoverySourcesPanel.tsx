"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { DiscoverySidecar } from "./types";

type DiscoverySourcesPanelProps = {
  onClose: () => void;
  sidecar: DiscoverySidecar;
};

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/**
 * A provider `source_date` is a calendar date, not an instant. Rendering it in
 * the viewer's zone would shift "2026-07-20" back a day west of UTC, so a
 * date-only value is formatted in UTC and stays the date the publisher stated.
 */
export function formattedSourceDate(
  value: string | null | undefined,
  locale: string,
): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    ...(DATE_ONLY.test(value) ? { timeZone: "UTC" } : {}),
  }).format(parsed);
}

/**
 * Evidence trail for one discovery turn. A pure renderer of the persisted
 * `metadata.discovery` sidecar — it never re-queries. Links open the publisher
 * in a new tab, and the visible domain always comes from the href being opened
 * so an untrusted provider title cannot disguise the destination.
 */
export default function DiscoverySourcesPanel({
  onClose,
  sidecar,
}: DiscoverySourcesPanelProps) {
  const { t, i18n } = useTranslation();
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    panel?.querySelector<HTMLElement>("[data-autofocus]")?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const focusable = panel.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
      restoreFocusRef.current?.focus?.();
    };
  }, [onClose]);

  const title = t("chat.discovery_results.sources_panel_title", {
    defaultValue: "Sources Argus read",
  });

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      <div
        aria-hidden="true"
        onClick={onClose}
        className="absolute inset-0 bg-black/25 dark:bg-black/50"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative flex max-h-full w-full flex-col self-end overflow-hidden rounded-t-2xl border border-black/10 bg-white shadow-none dark:border-white/10 dark:bg-[#1d2023] sm:max-w-[420px] sm:self-stretch sm:rounded-none sm:rounded-s-2xl sm:border-y-0 sm:border-e-0"
      >
        <div className="flex items-start justify-between gap-3 border-b border-black/8 px-4 py-3 dark:border-white/8">
          <div className="min-w-0">
            <p className="text-[14px] font-medium leading-[1.45] tracking-tight text-black dark:text-white">
              {title}
            </p>
            <p className="mt-0.5 text-[12px] leading-[1.5] text-black/50 dark:text-white/50">
              {t("chat.discovery_results.sources_panel_note", {
                defaultValue:
                  "Argus read these while answering. Not recommended reading.",
              })}
            </p>
          </div>
          <button
            type="button"
            data-autofocus
            onClick={onClose}
            aria-label={t("chat.discovery_results.sources_panel_close", {
              defaultValue: "Close sources",
            })}
            className="shrink-0 rounded-full p-1.5 text-black/60 transition-colors hover:bg-black/5 hover:text-black dark:text-white/60 dark:hover:bg-white/10 dark:hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <ul className="flex-1 overflow-y-auto px-4 py-2">
          {sidecar.sources.map((source) => {
            const date = formattedSourceDate(source.source_date, i18n.language);
            return (
              <li
                key={source.url}
                className="border-b border-black/6 py-3 last:border-b-0 dark:border-white/6"
              >
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group/source flex min-h-11 flex-col gap-1 text-start"
                >
                  {source.title ? (
                    <span className="text-[14px] leading-[1.45] tracking-tight text-black/80 [overflow-wrap:anywhere] group-hover/source:underline dark:text-white/80">
                      {source.title}
                    </span>
                  ) : null}
                  <span className="text-[12px] leading-[1.5] text-black/50 [overflow-wrap:anywhere] dark:text-white/50">
                    {source.domain}
                    {date ? ` · ${date}` : ""}
                  </span>
                </a>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
