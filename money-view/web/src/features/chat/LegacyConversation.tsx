import { ExternalLink } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { request, requestResponse } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import type { PlatformPageProps } from '../../platform/types';
import { EvidenceLine, Money } from '../../platform/ui';
import { detailSchema, type Fact } from '../assistant/contracts';
import { commandFieldLabel, copy, dateLabel } from './copy';

type Props = Pick<PlatformPageProps, 'locale' | 'onNavigate'> & { legacyId: string };

function LegacyFact({ fact, locale, onNavigate }: { fact: Fact; locale: Props['locale']; onNavigate: Props['onNavigate'] }) {
  const t = copy(locale);
  return <div className="argus-fact">
    <div className="argus-fact-main">
      <span>{fact.record_name ? `${fact.record_name} · ` : ''}{commandFieldLabel(fact.key, locale)}</span>
      {fact.unit === 'money' && fact.currency ? <Money amount={fact.value} currency={fact.currency} locale={locale} /> : <strong>{fact.value}{fact.unit === 'percent' ? '%' : ''}</strong>}
    </div>
    {fact.notes.includes('partial_unpriced_holdings') ? <p className="argus-card-note">{t.partial}</p> : null}
    <EvidenceLine evidence={fact.source} locale={locale} />
    <button className="argus-card-link" type="button" onClick={() => onNavigate(fact.target.page, { ...fact.target.query, ...(fact.target.record_ids[0] ? { record_id: fact.target.record_ids[0] } : {}) })}>{t.openRecord}<ExternalLink size={14}/></button>
  </div>;
}

export function LegacyConversation({ legacyId, locale, onNavigate }: Props) {
  const t = copy(locale);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const exportAbort = useRef<AbortController | null>(null);
  useEffect(() => () => exportAbort.current?.abort(), [legacyId]);
  const resource = useResource(() => request(`/assistant/conversations/${encodeURIComponent(legacyId)}`, detailSchema), [legacyId]);
  const exportSnapshot = async () => {
    setExporting(true); setExportError('');
    const controller = new AbortController();
    exportAbort.current = controller;
    try {
      const response = await requestResponse(`/assistant/conversations/${encodeURIComponent(legacyId)}/export`, { signal: controller.signal });
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = 'argus-conversation.json';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (caught) { if (!(caught instanceof DOMException && caught.name === 'AbortError')) setExportError(t.legacyExportError); }
    finally { if (!controller.signal.aborted) setExporting(false); }
  };
  return <main className="argus-conversation argus-legacy" data-testid="legacy-conversation">
    <header className="argus-conversation-header">
      <div><p className="p-eyebrow">{t.legacyTitle}</p><h1 tabIndex={-1}>{resource.data?.conversation.title ?? t.title}</h1><p>{t.legacyBody}</p></div>
    </header>
    <div className="argus-transcript" tabIndex={-1}>
      {resource.loading ? <p role="status" className="p-loading">{t.loading}</p> : resource.error ? <div className="p-inline-error" role="alert"><span>{t.loadError}</span><button className="p-button-secondary" onClick={resource.reload}>{t.retry}</button></div> : resource.data ? <>
        {resource.data.messages.filter((message) => message.role === 'user' && message.text).map((message) => <article className="argus-message argus-message-user" key={message.id}><p>{message.text}</p><time dateTime={message.created_at}>{dateLabel(message.created_at, locale, true)}</time></article>)}
        {resource.data.answers.map((answer) => <article className="argus-message argus-message-assistant argus-legacy-answer" key={answer.id}>
          <header><h2>{commandFieldLabel(answer.action, locale)}</h2><time dateTime={answer.created_at}>{dateLabel(answer.created_at, locale, true)}</time></header>
          {answer.facts.length ? <section className="argus-inline-card argus-read-card">{answer.facts.map((fact, index) => <LegacyFact fact={fact} locale={locale} onNavigate={onNavigate} key={`${fact.key}-${index}`}/>)}</section> : <p>{t.noFacts}</p>}
        </article>)}
      </> : null}
    </div>
    <footer className="argus-legacy-actions">
      {exportError ? <p className="p-error" role="alert">{exportError}</p> : null}
      <button className="p-button-secondary" type="button" disabled={exporting} onClick={() => void exportSnapshot()}>{t.legacyExport}</button>
      <button className="p-button-secondary" type="button" onClick={() => onNavigate('saved')}>{t.legacyOpenSaved}</button>
      <button className="p-button" type="button" onClick={() => onNavigate('chat', { new: crypto.randomUUID(), from_legacy: legacyId })}>{t.continueNew}</button>
    </footer>
  </main>;
}
