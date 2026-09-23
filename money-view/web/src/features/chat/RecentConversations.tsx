import { Ellipsis, Pin } from 'lucide-react';
import { useState, type FormEvent, type MouseEvent } from 'react';
import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import type { PlatformPageProps } from '../../platform/types';
import { conversationListSchema, conversationSchema, type Conversation, type ConversationState } from './contracts';
import { copy, dateLabel } from './copy';
import './chat.css';

export type RecentConversationsProps = Pick<PlatformPageProps, 'locale' | 'revision' | 'onNavigate'>;

export function RecentConversations({ locale, revision, onNavigate }: RecentConversationsProps) {
  const t = copy(locale);
  const [state, setState] = useState<ConversationState>('active');
  const [renaming, setRenaming] = useState<Conversation | null>(null);
  const [title, setTitle] = useState('');
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');
  const resource = useResource(
    () => request(`/chat/conversations?state=${state}&limit=8&offset=0`, conversationListSchema),
    [state, revision],
  );

  const closeMenu = (event: MouseEvent<HTMLElement>) => {
    const details = event.currentTarget.closest('details');
    if (details) details.open = false;
  };
  const update = async (item: Conversation, change: { title?: string; pinned?: boolean; state?: ConversationState }) => {
    setBusyId(item.id);
    setError('');
    try {
      await request(`/chat/conversations/${encodeURIComponent(item.id)}`, conversationSchema, { method: 'PATCH', body: JSON.stringify(change) });
      setRenaming(null);
      resource.reload();
    } catch {
      setError(t.genericError);
    } finally {
      setBusyId('');
    }
  };
  const submitRename = (event: FormEvent) => {
    event.preventDefault();
    if (renaming && title.trim()) void update(renaming, { title: title.trim() });
  };

  return <div className="argus-recent-list" data-testid="recent-conversations">
    <details className="argus-owner-menu argus-recent-filter" onKeyDown={(event) => { if (event.key === 'Escape') { event.currentTarget.open = false; event.currentTarget.querySelector('summary')?.focus(); } }}><summary aria-label={`${t.recent}: ${t[state]}`}><Ellipsis size={16}/></summary><div role="menu">{(['active', 'archived', 'trashed'] as const).map((value) => <button type="button" role="menuitemradio" aria-checked={state === value} key={value} onClick={(event) => { closeMenu(event); setState(value); }}>{t[value]}</button>)}</div></details>
    {resource.loading && !resource.data ? <p className="p-muted" role="status">{t.loading}</p> : resource.error ? <button className="argus-next-move" type="button" onClick={resource.reload}><span aria-hidden="true">↳</span>{t.retry}</button> : !resource.data?.items.length ? <p className="p-muted">{t.noConversations}</p> : <ul>{resource.data.items.map((item) => <li key={item.id} data-conversation-id={item.id}>
      {renaming?.id === item.id ? <form className="argus-recent-rename" onSubmit={submitRename}><label><span className="sr-only">{t.titleLabel}</span><input autoFocus maxLength={120} value={title} onChange={(event) => setTitle(event.target.value)} /></label><button className="p-button-ghost" disabled={busyId === item.id || !title.trim()}>{t.save}</button><button type="button" className="p-button-ghost" onClick={() => setRenaming(null)}>{t.cancel}</button></form> : <>
        <button className="argus-recent-open" type="button" onClick={() => onNavigate('chat', { conversation_id: item.id })}><span>{item.pinned ? <Pin size={12} aria-label={t.pin}/> : null}{item.title}</span><small>{dateLabel(item.updated_at, locale, true)}</small></button>
        <details className="argus-owner-menu" onKeyDown={(event) => { if (event.key === 'Escape') { event.currentTarget.open = false; event.currentTarget.querySelector('summary')?.focus(); } }}><summary aria-label={t.conversationMenu}><Ellipsis size={18}/></summary><div role="menu">
          <button type="button" role="menuitem" disabled={busyId === item.id} onClick={(event) => { closeMenu(event); setTitle(item.title); setRenaming(item); }}>{t.rename}</button>
          <button type="button" role="menuitem" disabled={busyId === item.id} onClick={(event) => { closeMenu(event); void update(item, { pinned: !item.pinned }); }}>{item.pinned ? t.unpin : t.pin}</button>
          {item.state === 'active' ? <button type="button" role="menuitem" disabled={busyId === item.id} onClick={(event) => { closeMenu(event); void update(item, { state: 'archived' }); }}>{t.archive}</button> : <button type="button" role="menuitem" disabled={busyId === item.id} onClick={(event) => { closeMenu(event); void update(item, { state: 'active' }); }}>{t.restore}</button>}
          {item.state !== 'trashed' ? <button type="button" role="menuitem" disabled={busyId === item.id} onClick={(event) => { closeMenu(event); void update(item, { state: 'trashed' }); }}>{t.trash}</button> : null}
        </div></details>
      </>}
    </li>)}</ul>}
    {error ? <p className="p-error" role="alert">{error}</p> : null}
  </div>;
}
