import type { ComparisonResult, Locale, Notice } from '../contracts';
import { copy, percent } from '../i18n';
import type { Receipt } from './ReceiptDrawer';
import { SourceLink } from './SourceLink';

export function NoticeEvidence({
  notice,
  original,
  locale,
  onReceipt,
}: {
  notice: Notice;
  original: ComparisonResult | undefined;
  locale: Locale;
  onReceipt: (receipt: Receipt) => void;
}) {
  const t = copy(locale);
  const reference = notice.reference_annual_rate_pct;
  const statedRate = original?.inputs.current_annual_rate_pct;
  const referenceRows =
    original && reference !== null && statedRate === null
      ? original.rows.filter(
          (row) => !row.is_baseline && row.effective_annual_rate_pct === reference,
        )
      : [];

  return (
    <div className="notice-evidence">
      {notice.reasons.includes('winner_changed') &&
        notice.after.rows
          .filter((row) => notice.after.winner_ids.includes(row.id))
          .map((row) => (
            <div key={row.id}>
              <span className="small">{row.is_baseline ? t.current : row.institution}</span>
              <SourceLink
                source={row.source}
                locale={locale}
                onOpen={() => onReceipt({ kind: 'result', result: notice.after, row })}
              />
            </div>
          ))}
      {notice.reasons.includes('inflation_crossed') && (
        <>
          <div>
            <p className="small">
              {t.inflation}: {percent(notice.after.inflation.annual_rate_pct, locale)}
            </p>
            <SourceLink
              source={notice.after.inflation.source}
              locale={locale}
              onOpen={() => onReceipt({ kind: 'source', source: notice.after.inflation.source })}
            />
          </div>
          {original && reference !== null && (
            <div>
              <p className="small">
                {t.referenceRate}:{' '}
                <span title={`${reference}%`} aria-label={`${reference}%`}>
                  {percent(reference, locale)}
                </span>{' '}
                · {statedRate !== null ? t.currentRate : t.savedReference}
              </p>
              {statedRate !== null ? (
                <SourceLink
                  source={original.input_source}
                  locale={locale}
                  onOpen={() => {
                    const row = original.rows.find((item) => item.is_baseline);
                    if (row) onReceipt({ kind: 'result', result: original, row });
                  }}
                />
              ) : (
                referenceRows.map((row) => (
                  <div key={row.id}>
                    <span className="small">{row.institution}</span>
                    <SourceLink
                      source={row.source}
                      locale={locale}
                      onOpen={() => onReceipt({ kind: 'result', result: original, row })}
                    />
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
