"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { businessContent, type BusinessLocale } from "./content";
import {
  formatSampleMoney,
  getSampleSummary,
  sampleExpenses,
  sampleMonths,
  sampleReceivables,
} from "./sample-data";
import styles from "./business.module.css";

function Receivables({
  locale,
  expanded = false,
}: {
  locale: BusinessLocale;
  expanded?: boolean;
}) {
  const copy = businessContent[locale].preview;
  return (
    <div className={expanded ? styles.receivablesExpanded : styles.receivables}>
      <h3>{copy.pending}</h3>
      {expanded && (
        <p className={styles.previewDescription}>{copy.pendingNote}</p>
      )}
      <ul className={styles.invoiceList}>
        {sampleReceivables.map((invoice) => (
          <li key={invoice.id}>
            <div>
              <strong>
                {copy.client} {invoice.customer}
              </strong>
              <span>
                {copy.invoice} #{invoice.id} · {copy.due} {invoice.day}{" "}
                {copy.months[4].toLowerCase()}
              </span>
            </div>
            <span className={styles.invoiceAmount}>
              {formatSampleMoney(invoice.amount, locale)}
            </span>
          </li>
        ))}
      </ul>
      {expanded && (
        <div className={styles.totalRow}>
          <span>{copy.total}</span>
          <strong>
            {formatSampleMoney(getSampleSummary().receivables, locale)}
          </strong>
        </div>
      )}
    </div>
  );
}

function CashChart({ locale }: { locale: BusinessLocale }) {
  const copy = businessContent[locale].preview;
  const max = Math.max(
    ...sampleMonths.flatMap((month) => [month.income, month.expenses]),
  );
  return (
    <div className={styles.cashChart}>
      <div className={styles.chartHeading}>
        <h3>{copy.cash}</h3>
        <div className={styles.legend}>
          <span>
            <i />
            {copy.income}
          </span>
          <span>
            <i />
            {copy.expenses}
          </span>
        </div>
      </div>
      <div className={styles.chart} aria-hidden="true">
        {sampleMonths.map((month, index) => (
          <div className={styles.monthBar} key={index}>
            <div className={styles.barPair}>
              <span style={{ height: `${(month.income / max) * 100}%` }} />
              <span style={{ height: `${(month.expenses / max) * 100}%` }} />
            </div>
            <span className={styles.monthLabel}>{copy.months[index]}</span>
          </div>
        ))}
      </div>
      <div className={styles.srOnly}>
        <table>
          <caption>{copy.chartLabel}</caption>
          <thead>
            <tr>
              <th scope="col">{copy.month}</th>
              <th scope="col">{copy.income}</th>
              <th scope="col">{copy.expenses}</th>
            </tr>
          </thead>
          <tbody>
            {sampleMonths.map((month, index) => (
              <tr key={index}>
                <th scope="row">{copy.months[index]}</th>
                <td>{formatSampleMoney(month.income, locale)}</td>
                <td>{formatSampleMoney(month.expenses, locale)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ProductPreview({ locale }: { locale: BusinessLocale }) {
  const [active, setActive] = useState(0);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const copy = businessContent[locale].preview;
  const summary = getSampleSummary();
  const onTabKey = (
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ): void => {
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % copy.tabs.length;
    else if (event.key === "ArrowLeft")
      next = (index - 1 + copy.tabs.length) % copy.tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = copy.tabs.length - 1;
    else return;
    event.preventDefault();
    setActive(next);
    tabs.current[next]?.focus();
  };
  return (
    <section
      className={styles.preview}
      id="la-idea"
      aria-labelledby="preview-title"
    >
      <div className={styles.previewHeader}>
        <div>
          <h2 id="preview-title">{copy.title}</h2>
          <p>{copy.note}</p>
        </div>
        <div className={styles.tabs} role="tablist" aria-label={copy.tablist}>
          {copy.tabs.map((label, index) => (
            <button
              key={label}
              ref={(element) => {
                tabs.current[index] = element;
              }}
              id={`preview-tab-${index}`}
              type="button"
              role="tab"
              aria-selected={active === index}
              aria-controls={`preview-panel-${index}`}
              tabIndex={active === index ? 0 : -1}
              onClick={() => setActive(index)}
              onKeyDown={(event) => onTabKey(event, index)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div
        id={`preview-panel-${active}`}
        role="tabpanel"
        tabIndex={0}
        aria-labelledby={`preview-tab-${active}`}
        className={styles.previewPanel}
      >
        {active === 0 && (
          <div className={styles.overview}>
            <div className={styles.overviewMain}>
              <div className={styles.metricPeriod}>{copy.monthLabel}</div>
              <div className={styles.metrics}>
                {[
                  { label: copy.income, value: summary.income },
                  { label: copy.expenses, value: summary.expenses },
                  { label: copy.difference, value: summary.difference },
                ].map((metric) => (
                  <div key={metric.label}>
                    <span>{metric.label}</span>
                    <strong>{formatSampleMoney(metric.value, locale)}</strong>
                    <div className={styles.metricTrack} aria-hidden="true">
                      <i
                        style={{
                          width: `${(metric.value / summary.income) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <CashChart locale={locale} />
            </div>
            <Receivables locale={locale} />
          </div>
        )}
        {active === 1 && <Receivables locale={locale} expanded />}
        {active === 2 && (
          <div className={styles.expensesView}>
            <div className={styles.expenseIntro}>
              <h3>{copy.expenseTitle}</h3>
              <p>{copy.expenseNote}</p>
              <span>{copy.monthLabel}</span>
              <strong>{formatSampleMoney(summary.expenses, locale)}</strong>
              <small>{copy.expenseTotal}</small>
            </div>
            <table className={styles.expenseTable}>
              <thead>
                <tr>
                  <th scope="col">{copy.category}</th>
                  <th scope="col">{copy.tableAmount}</th>
                </tr>
              </thead>
              <tbody>
                {sampleExpenses.map((item) => (
                  <tr key={item.category}>
                    <th scope="row">{copy.expenseLabels[item.category]}</th>
                    <td>{formatSampleMoney(item.amount, locale)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">{copy.expenseTotal}</th>
                  <td>{formatSampleMoney(summary.expenses, locale)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
