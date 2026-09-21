import { request } from "../../platform/client";
import { useResource } from "../../platform/hooks";
import {
  PageHeader,
  Panel,
  Field,
  EvidenceLine,
  Money,
  EmptyState,
} from "../../platform/ui";
import type { PlatformPageProps } from "../../platform/types";
import { spendingSchema } from "./contracts";
import { copy, categoryLabel } from "./copy";
import { ResourceState } from "./shared";
import "./ledger.css";

export function SpendingPage({
  locale,
  currency,
  query,
  revision,
  onNavigate,
}: PlatformPageProps) {
  const t = copy(locale),
    month = query.get("month") || new Date().toISOString().slice(0, 7);
  const spending = useResource(
    () =>
      request(
        `/spending?month=${encodeURIComponent(month)}&currency=${encodeURIComponent(currency)}`,
        spendingSchema,
      ),
    [month, currency, revision],
  );
  const data = spending.data;
  const peak = Math.max(
    1,
    ...(data?.categories.map((item) => Math.abs(Number(item.amount))) ?? []),
  );
  const drill = (filters: Record<string, string>) => {
    const [year, monthNumber] = month.split("-").map(Number),
      lastDay = new Date(Date.UTC(year, monthNumber, 0))
        .toISOString()
        .slice(0, 10);
    onNavigate("transactions", {
      date_from: `${month}-01`,
      date_to: lastDay,
      spending_only: "true",
      ...filters,
    });
  };
  return (
    <div className="ledger-page p-stack">
      <PageHeader
        title={t.spending}
        description={t.spendingIntro}
        actions={
          <Field label={t.month}>
            <input
              type="month"
              value={month}
              required
              onChange={(e) => {
                if (e.target.value)
                  onNavigate("spending", { month: e.target.value });
              }}
            />
          </Field>
        }
      />
      <p className="p-muted">
        {currency} · {t.noConversion}
      </p>
      <ResourceState {...spending} retry={spending.reload} locale={locale} />
      {data && (
        <>
          <Panel>
            <h2>{t.periodTotals}</h2>
            <div className="p-metrics">
              {(["income", "spending", "net"] as const).map((metric) => (
                <div className="p-metric" key={metric}>
                  <small>{t[metric]}</small>
                  <strong>
                    <Money
                      amount={data[metric]}
                      currency={data.currency}
                      locale={locale}
                    />
                  </strong>
                </div>
              ))}
            </div>
            <p className="p-muted">{t.spendingNote}</p>
            <EvidenceLine evidence={data.source} locale={locale} />
          </Panel>
          <Panel>
            <div className="p-toolbar">
              <h2>{t.categories}</h2>
              <button className="p-button-ghost" onClick={() => drill({})}>
                {t.viewTransactions}
              </button>
            </div>
            {!data.categories.length ? (
              <EmptyState title={t.noSpending} />
            ) : (
              <ul className="ledger-bars">
                {data.categories.map((item) => (
                  <li key={item.category}>
                    <button
                      className="ledger-bar-link"
                      onClick={() => drill({ category: item.category })}
                      aria-label={`${t.matching} ${categoryLabel(item.category, locale)}`}
                    >
                      <span className="ledger-bar-heading">
                        <span>
                          {categoryLabel(item.category, locale)}
                          <small className="ledger-subline">
                            {item.transaction_count.toLocaleString(locale)}{" "}
                            {t.transactions.toLowerCase()}
                          </small>
                        </span>
                        <strong>
                          <Money
                            amount={item.amount}
                            currency={data.currency}
                            locale={locale}
                          />
                        </strong>
                      </span>
                      <span className="ledger-bar-track" aria-hidden="true">
                        <span
                          style={{
                            width: `${(Math.abs(Number(item.amount)) / peak) * 100}%`,
                          }}
                        />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <EvidenceLine evidence={data.source} locale={locale} />
          </Panel>
          <Panel>
            <h2>{t.merchants}</h2>
            {!data.merchants.length ? (
              <EmptyState title={t.noMerchants} />
            ) : (
              <div className="p-ledger">
                {data.merchants.map((item) => (
                  <article className="p-ledger-row" key={item.merchant}>
                    <div className="p-row-main">
                      <h3>{item.merchant}</h3>
                      <span className="p-muted">
                        {item.transaction_count.toLocaleString(locale)}{" "}
                        {t.transactions.toLowerCase()}
                      </span>
                    </div>
                    <div className="p-row-value">
                      <Money
                        amount={item.amount}
                        currency={data.currency}
                        locale={locale}
                      />
                    </div>
                    <button
                      className="p-button-ghost"
                      onClick={() => drill({ merchant: item.merchant })}
                      aria-label={`${t.matching} ${item.merchant}`}
                    >
                      {t.viewTransactions}
                    </button>
                  </article>
                ))}
              </div>
            )}
            <EvidenceLine evidence={data.source} locale={locale} />
          </Panel>
        </>
      )}
    </div>
  );
}
