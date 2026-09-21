import { useEffect, useRef, useState } from 'react';
import { ExternalLink, X } from 'lucide-react';
import type { Locale, Source } from '../contracts';
import { api } from '../api';
import { copy, date, money, percent } from '../i18n';
import type { ReceiptSelection } from './Comparison';
export type Receipt = ReceiptSelection | { kind: 'source'; source: Source };

function SourceDocument({ source, locale }: { source: Source; locale: Locale }) {
  const t = copy(locale);
  const [document, setDocument] = useState<
    { state: 'loading' } | { state: 'ready'; data: unknown } | { state: 'error' }
  >({ state: 'loading' });
  useEffect(() => {
    let active = true;
    setDocument({ state: 'loading' });
    void api.source(source.id).then(
      (data) => {
        if (active) setDocument({ state: 'ready', data });
      },
      () => {
        if (active) setDocument({ state: 'error' });
      },
    );
    return () => {
      active = false;
    };
  }, [source.id]);
  const safeUrl =
    source.url.startsWith('/api/sources/') || /^https?:\/\//.test(source.url)
      ? source.url
      : `/api/sources/${encodeURIComponent(source.id)}`;
  return (
    <section className="receipt-source">
      <h3>{source.title}</h3>
      <p>
        {source.kind === 'synthetic' ? t.receiptDate : t.publishedDate}:{' '}
        {date(source.published_on, locale)}
      </p>
      <a href={safeUrl} target="_blank" rel="noreferrer">
        {t.sourceDocument}
        <ExternalLink size={14} aria-hidden="true" />
      </a>
      {document.state === 'loading' && <p role="status">{t.sourceLoading}</p>}
      {document.state === 'error' && <p role="alert">{t.sourceError}</p>}
      {document.state === 'ready' && (
        <details>
          <summary>{t.sourceRaw}</summary>
          <pre>{JSON.stringify(document.data, null, 2)}</pre>
        </details>
      )}
    </section>
  );
}
export function ReceiptDrawer({
  receipt,
  locale,
  onClose,
}: {
  receipt: Receipt;
  locale: Locale;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const t = copy(locale);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  const result = receipt.kind === 'result' ? receipt.result : null;
  const row = receipt.kind === 'result' ? receipt.row : null;
  return (
    <dialog
      ref={dialog}
      className="receipt-dialog"
      data-testid="receipt-dialog"
      aria-labelledby="receipt-title"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="drawer-header">
        <h2 id="receipt-title">{t.sourceAndMath}</h2>
        <button className="icon-button" onClick={onClose} aria-label={t.close} autoFocus>
          <X size={23} />
        </button>
      </div>
      <div className="drawer-body">
        {result && row && (
          <>
            <h3>{row.is_baseline ? t.current : row.institution}</h3>
            <dl className="receipt-figures">
              <div>
                <dt>{t.finalValue}</dt>
                <dd>{money(row.end_value, result.inputs.currency, locale)}</dd>
              </div>
              <div>
                <dt>{t.realValue}</dt>
                <dd>{money(row.real_value, result.inputs.currency, locale)}</dd>
              </div>
              <div>
                <dt>{t.interest}</dt>
                <dd>{money(row.interest, result.inputs.currency, locale)}</dd>
              </div>
              <div>
                <dt>{t.fees}</dt>
                <dd>{money(row.fees, result.inputs.currency, locale)}</dd>
              </div>
              <div>
                <dt>{t.effective}</dt>
                <dd>{percent(row.effective_annual_rate_pct, locale)}</dd>
              </div>
            </dl>
            <section className="receipt-source">
              <h3>{t.inputs}</h3>
              <p>
                {money(result.inputs.amount, result.inputs.currency, locale)} ·{' '}
                {result.inputs.horizon_days} {t.days} · {result.inputs.country}
              </p>
              <p>
                {t.recorded} {date(result.input_source.recorded_on, locale)}
              </p>
              <p>
                {t.currentRate}:{' '}
                {result.inputs.current_annual_rate_pct === null
                  ? t.assumption
                  : percent(result.inputs.current_annual_rate_pct, locale)}
              </p>
            </section>
            {'id' in row.source ? (
              <SourceDocument source={row.source} locale={locale} />
            ) : (
              <section className="receipt-source">
                <h3>{row.source.kind === 'assumption' ? t.assumption : t.userSource}</h3>
                <p>
                  {t.recorded} {date(row.source.recorded_on, locale)} ·{' '}
                  {percent(row.annual_rate_pct, locale)}
                </p>
              </section>
            )}
            {row.fee_source &&
              row.fee_source.id !== ('id' in row.source ? row.source.id : null) && (
                <SourceDocument source={row.fee_source} locale={locale} />
              )}
            <SourceDocument source={result.inflation.source} locale={locale} />
            <section className="formula">
              <h3>{t.formula}</h3>
              <p>{t.rounding}</p>
              <p>{t.interestFormula}</p>
              <code>
                {row.formula.amount} × {row.formula.annual_rate_pct} / 100 ×{' '}
                {row.formula.horizon_days} / 365 ≈ {row.formula.interest}
              </code>
              <p>{t.nominalFormula}</p>
              <code>
                {row.formula.amount} + {row.formula.interest} − {row.formula.fee_amount} ≈{' '}
                {row.formula.nominal_end_value}
              </code>
              <p>{t.realFormula}</p>
              <code>
                {row.formula.nominal_end_value} /{' '}
                {new Intl.NumberFormat(locale, { maximumFractionDigits: 6 }).format(
                  Number(row.formula.inflation_factor),
                )}{' '}
                ≈ {row.formula.real_value}
              </code>
            </section>
            <section className="assumptions">
              <h3>{t.assumptions}</h3>
              <p>{t.simpleRate}</p>
              <p>{t.constantInflation}</p>
              <p>{t.noTaxes}</p>
              <p>{t.noFx}</p>
            </section>
          </>
        )}
        {receipt.kind === 'source' && <SourceDocument source={receipt.source} locale={locale} />}
        <p className="disclosure">{t.disclosure}</p>
      </div>
    </dialog>
  );
}
