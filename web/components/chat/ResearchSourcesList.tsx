import { ExternalLink } from "lucide-react";
import type { DiscoverySource } from "./types";
import type { ToolTranslator } from "@/lib/tool-result-card";

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

/** One citation list serves the existing drawer, tool cards and public receipts. */
export default function ResearchSourcesList({ sources, locale, t, anchorIndex = null }: {
  sources: DiscoverySource[]; locale: string; t: ToolTranslator; anchorIndex?: number | null;
}) {
  return (
    <ul className="flex-1 overflow-y-auto px-4 py-2">
      {sources.map((source, index) => {
        const date = formattedSourceDate(source.source_date, locale);
        return (
          <li
            key={source.url}
            data-source-index={index}
            className={`border-b border-black/6 py-3 last:border-b-0 dark:border-white/6 ${
              index === anchorIndex
                ? "-mx-2 rounded-lg bg-[#5ba897]/[0.08] px-2"
                : ""
            }`}
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
              <span className="inline-flex items-center gap-1 text-[13px] font-medium leading-[1.5] text-black/70 [overflow-wrap:anywhere] dark:text-white/70">
                <span>
                  {source.domain}
                  {date ? ` · ${date}` : ""}
                </span>
                <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span className="sr-only">
                  {t(
                    "chat.discovery_results.sources_panel_external_link_new_tab",
                    { defaultValue: "Opens in a new tab" },
                  )}
                </span>
              </span>
            </a>
          </li>
        );
      })}
    </ul>
  );
}
