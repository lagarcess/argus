import type { ComparisonResult, ComparisonRow, Locale } from '../contracts';
import { copy, date, money, percent } from '../i18n';
import { SourceLink } from './SourceLink';

export type ReceiptSelection = { kind: 'result'; result: ComparisonResult; row: ComparisonRow };
export function Comparison({
  result,
  locale,
  onReceipt,
  title,
}: {
  result: ComparisonResult;
  locale: Locale;
  onReceipt: (selection: ReceiptSelection) => void;
  title?: string;
}) {
  const t = copy(locale);
  const baseline = result.rows.filter((row) => row.is_baseline);
  const deposits = result.rows.filter((row) => !row.is_baseline);
  const renderRow = (row: ComparisonRow) => {
    const receiptId = `receipt-${result.id}-${row.id}`;
    const endValue = money(row.end_value, result.inputs.currency, locale);
    return (
      <article
        key={row.id}
        className={`comparison-row ${result.winner_ids.includes(row.id) ? 'leading' : ''} ${endValue.length > 18 ? 'long-amount' : ''}`}
        aria-describedby={`${receiptId} context-${result.id}`}
      >
        <div className="institution">
          <h3>{row.is_baseline ? t.current : row.institution}</h3>
          <div id={receiptId}>
            <SourceLink
              source={row.source}
              locale={locale}
              onOpen={() => onReceipt({ kind: 'result', result, row })}
            />
          </div>
        </div>
        <div className="rate-figure">
          <strong>{percent(row.annual_rate_pct, locale)}</strong>
          <span>{row.is_baseline ? t.currentRate : t.averageRate}</span>
        </div>
        <div className="end-figure">
          <strong>{endValue}</strong>
          <span>{t.finalValue}</span>
        </div>
      </article>
    );
  };
  return (
    <section className="comparison" data-testid="comparison" aria-label={title ?? t.comparison}>
      {title && <h2 className="comparison-title">{title}</h2>}
      {baseline.map(renderRow)}
      <div className="section-heading">
        <h2>
          {t.comparison} · {result.inputs.horizon_days} {t.days}
        </h2>
        <span>{result.synthetic ? t.illustration : ''}</span>
      </div>
      <div className="comparison-rows">{deposits.map(renderRow)}</div>
      <div className="comparison-context" id={`context-${result.id}`}>
        <p>
          {t.inflation}: <strong>{percent(result.inflation.annual_rate_pct, locale)}</strong>
        </p>
        <SourceLink
          source={result.inflation.source}
          locale={locale}
          onOpen={() => {
            const row = result.rows[0];
            if (row) onReceipt({ kind: 'result', result, row });
          }}
        />
        <p>
          {t.inputs} · {money(result.inputs.amount, result.inputs.currency, locale)} ·{' '}
          {result.inputs.horizon_days} {t.days}
          <br />
          {t.recorded} {date(result.input_source.recorded_on, locale)}
        </p>
      </div>
    </section>
  );
}
