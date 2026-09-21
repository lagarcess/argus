import { FileText } from 'lucide-react';
import type { InputSource, Locale, Source } from '../contracts';
import { copy, date } from '../i18n';

export function SourceLink({
  source,
  locale,
  onOpen,
}: {
  source: Source | InputSource;
  locale: Locale;
  onOpen: () => void;
}) {
  const t = copy(locale);
  const label =
    source.kind === 'synthetic'
      ? t.syntheticSource
      : source.kind === 'published'
        ? t.publishedSource
        : source.kind === 'user'
          ? t.userSource
          : t.assumption;
  const recorded = 'published_on' in source ? source.published_on : source.recorded_on;
  return (
    <button type="button" data-testid="source-link" className="source-link" onClick={onOpen}>
      <FileText size={15} aria-hidden="true" />
      <span>
        {label} · {date(recorded, locale)}
      </span>
    </button>
  );
}
