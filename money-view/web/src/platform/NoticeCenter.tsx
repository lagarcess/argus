import { useState } from "react";
import { Bell, ArrowRight, ChevronLeft, ChevronRight } from "lucide-react";
import { z } from "zod";
import { request } from "./client";
import { useResource } from "./hooks";
import { EmptyState, EvidenceLine, Modal } from "./ui";
import type { Locale, PlatformPageProps } from "./types";
import { insightsSchema } from "../features/assistant/contracts";
import { copy as assistantCopy, label } from "../features/assistant/catalog";
import "./notices.css";

const summarySchema = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      decision_id: z.string(),
      created_at: z.string(),
      reasons: z.array(z.string()),
      read_at: z.string().nullable(),
      source_dates: z.array(
        z.object({
          published_on: z.string(),
          kind: z.enum(["synthetic", "published"]),
          title: z.string(),
        }),
      ),
    }),
  ),
  unread_count: z.number().int().nonnegative(),
  total: z.number().int().nonnegative(),
});
const PAGE_SIZE = 20;

export function NoticeCenter({
  locale,
  currency,
  revision,
  routeKey,
  onNavigate,
}: Pick<
  PlatformPageProps,
  "locale" | "currency" | "revision" | "onNavigate"
> & { routeKey: string }) {
  const en = locale === "en";
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const result = useResource(async () => {
    const [deposits, signals] = await Promise.allSettled([
      request(
        `/api/notices/summary?limit=${PAGE_SIZE}&offset=${offset}`,
        summarySchema,
      ),
      request(
        `/insights?currency=${encodeURIComponent(currency)}`,
        insightsSchema,
      ),
    ]);
    return { deposits, signals };
  }, [currency, revision, routeKey, offset]);
  const deposits =
    result.data?.deposits.status === "fulfilled"
      ? result.data.deposits.value
      : null;
  const signals =
    result.data?.signals.status === "fulfilled"
      ? result.data.signals.value.notices.filter(
          (item) => item.state !== "dismissed",
        )
      : [];
  const unread =
    (deposits?.unread_count ?? 0) +
    signals.filter((item) => item.state === "unread").length;
  const failedDeposits =
    result.error || result.data?.deposits.status === "rejected";
  const failedSignals =
    result.error || result.data?.signals.status === "rejected";
  const sourceDate = (value: string) =>
    new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }).format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value));
  const go: PlatformPageProps["onNavigate"] = (page, query) => {
    setOpen(false);
    onNavigate(page, query);
  };
  const heading = (reasons: string[]) =>
    reasons.includes("winner_changed")
      ? en
        ? "A deposit comparison has a new leader"
        : "Una comparación de depósitos tiene un nuevo líder"
      : en
        ? "A deposit comparison changed relative to inflation"
        : "Una comparación de depósitos cambió frente a la inflación";
  return (
    <>
      <button
        type="button"
        className="p-icon-button p-notice-trigger"
        aria-label={`${en ? "Notices" : "Avisos"}${unread > 0 ? ` (${unread})` : ""}`}
        onClick={() => {
          setOpen(true);
          result.reload();
        }}
      >
        <Bell size={18} />
        {unread > 0 && (
          <span className="p-notice-count" aria-hidden="true">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <Modal
          title={en ? "Your notices" : "Tus avisos"}
          onClose={() => setOpen(false)}
        >
          <div className="p-notice-center">
            <p className="p-muted">
              {en
                ? "Dated changes from your saved comparisons and household records. Open a record to review its evidence."
                : "Cambios con fecha de tus comparaciones guardadas y registros del hogar. Abre un registro para revisar su evidencia."}
            </p>
            {result.loading && (
              <p className="p-muted" role="status">
                {en ? "Refreshing notices…" : "Actualizando avisos…"}
              </p>
            )}
            {failedDeposits && (
              <div className="p-notice-error" role="alert">
                <p>
                  {en
                    ? "Deposit notices could not be loaded."
                    : "No se pudieron cargar los avisos de depósitos."}
                </p>
                <button className="p-button-secondary" onClick={result.reload}>
                  {en ? "Retry" : "Reintentar"}
                </button>
              </div>
            )}
            {deposits && deposits.items.length > 0 && (
              <section>
                <h3>
                  {en
                    ? "Saved deposit comparisons"
                    : "Comparaciones de depósitos guardadas"}
                </h3>
                {deposits.items.map((notice) => (
                  <article key={notice.id} className="p-notice-row">
                    <div className="p-notice-row-heading">
                      <span className="p-badge">
                        {notice.read_at
                          ? en
                            ? "Read"
                            : "Leído"
                          : en
                            ? "Unread"
                            : "Sin leer"}
                      </span>
                      <time dateTime={notice.created_at}>
                        {sourceDate(notice.created_at)}
                      </time>
                    </div>
                    <button
                      className="p-notice-link"
                      onClick={() =>
                        go("deposits", {
                          decision: notice.decision_id,
                          notice: notice.id,
                        })
                      }
                    >
                      <strong>{heading(notice.reasons)}</strong>
                      <ArrowRight size={18} />
                    </button>
                    <div className="p-notice-source-dates">
                      {notice.source_dates.map((source, index) => (
                        <p
                          key={`${source.title}:${source.published_on}:${index}`}
                        >
                          {source.kind === "synthetic"
                            ? en
                              ? "Simulated source"
                              : "Fuente simulada"
                            : en
                              ? "Published source"
                              : "Fuente publicada"}{" "}
                          · {sourceDate(source.published_on)}
                          <span>{source.title}</span>
                        </p>
                      ))}
                    </div>
                    <p className="p-muted">
                      {en
                        ? "Open the before and after comparison"
                        : "Abrir la comparación antes y después"}
                    </p>
                  </article>
                ))}
                <div className="p-pagination">
                  <button
                    className="p-icon-button"
                    aria-label={en ? "Previous notices" : "Avisos anteriores"}
                    disabled={offset === 0 || result.loading}
                    onClick={() =>
                      setOffset((value) => Math.max(0, value - PAGE_SIZE))
                    }
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <span>
                    {offset + 1}–{Math.min(offset + PAGE_SIZE, deposits.total)}{" "}
                    / {deposits.total}
                  </span>
                  <button
                    className="p-icon-button"
                    aria-label={en ? "Next notices" : "Avisos siguientes"}
                    disabled={
                      offset + PAGE_SIZE >= deposits.total || result.loading
                    }
                    onClick={() => setOffset((value) => value + PAGE_SIZE)}
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>
              </section>
            )}
            {failedSignals && (
              <div className="p-notice-error" role="alert">
                <p>
                  {en
                    ? "Household signals could not be loaded."
                    : "No se pudieron cargar las señales del hogar."}
                </p>
                <button className="p-button-secondary" onClick={result.reload}>
                  {en ? "Retry" : "Reintentar"}
                </button>
              </div>
            )}
            {signals.length > 0 && (
              <section>
                <h3>{en ? "Household records" : "Registros del hogar"}</h3>
                {signals.map((notice) => (
                  <article key={notice.id} className="p-notice-row">
                    <button
                      className="p-notice-link"
                      onClick={() =>
                        go(notice.fact.target.page, notice.fact.target.query)
                      }
                    >
                      <strong>
                        {label(assistantCopy(locale).notices, notice.code)}
                      </strong>
                      <ArrowRight size={18} />
                    </button>
                    <EvidenceLine
                      evidence={notice.fact.source}
                      locale={locale}
                    />
                  </article>
                ))}
              </section>
            )}
            {!result.loading &&
              !failedDeposits &&
              !failedSignals &&
              deposits?.total === 0 &&
              signals.length === 0 && (
                <EmptyState
                  title={en ? "No notices yet" : "Todavía no hay avisos"}
                  description={
                    en
                      ? "Changes to saved comparisons and available household checks will appear here."
                      : "Los cambios en comparaciones guardadas y las comprobaciones disponibles aparecerán aquí."
                  }
                />
              )}
          </div>
        </Modal>
      )}
    </>
  );
}
