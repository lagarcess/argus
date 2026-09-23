import { ArrowDown, Copy, Ellipsis, Pin, RotateCcw, Square } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent } from 'react';
import { ArgusComposer, type ArgusComposerHandle, type ComposerDraftSnapshot, type Mention } from '../../argus/ArgusComposer';
import { APIError, request, requestResponse } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import type { PlatformPageProps } from '../../platform/types';
import { ChatCardView } from './cards';
import {
  capabilitiesSchema,
  contextSchema,
  conversationDetailSchema,
  conversationSchema,
  proposalConfirmSchema,
  proposalMutationSchema,
  type ChatMessage,
  type Conversation,
  type ConversationDetail,
  type ConversationState,
  type PreparedAction,
  type Proposal,
} from './contracts';
import { copy, dateLabel } from './copy';
import { clearChatDraft, conversationDraftKey, markChatDraftSubmitted, readChatDraft, stagedChatTurnId, updateChatDraftText } from './drafts';
import { LegacyConversation } from './LegacyConversation';
import { streamTurn, turnCurrencyContext, type TurnPayload } from './stream';
import './chat.css';

type Stage = 'interpret' | 'execute' | '';

function errorCopy(error: unknown, locale: PlatformPageProps['locale']) {
  const t = copy(locale);
  if (!(error instanceof APIError)) return t.genericError;
  if (error.code === 'conversation_inactive') return t.conversationInactive;
  if (error.code === 'conversation_busy') return t.conversationBusy;
  if (error.code === 'context_too_large') return t.contextTooLarge;
  if (['command_currency_mismatch', 'account_currency_mismatch', 'currency_context_mismatch'].includes(error.code)) return t.currencyMismatch;
  if (error.code === 'model_unavailable') return t.modelUnavailable;
  if (error.code === 'invalid_response' || error.code === 'stream_incomplete') return t.invalidResponse;
  return t.sendError;
}

function OwnerMenu({ conversation, locale, busy, onUpdate, onExport }: {
  conversation: Conversation;
  locale: PlatformPageProps['locale'];
  busy: boolean;
  onUpdate: (change: { title?: string; pinned?: boolean; state?: ConversationState }) => void;
  onExport: () => void;
}) {
  const t = copy(locale);
  const [rename, setRename] = useState(false);
  const [title, setTitle] = useState(conversation.title);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (title.trim()) { onUpdate({ title: title.trim() }); setRename(false); }
  };
  const apply = (event: MouseEvent<HTMLButtonElement>, change: { title?: string; pinned?: boolean; state?: ConversationState }) => {
    const details = event.currentTarget.closest('details');
    if (details) details.open = false;
    onUpdate(change);
  };
  return <div className="argus-header-actions">
    {rename ? <form className="argus-title-form" onSubmit={submit}><label><span className="sr-only">{t.titleLabel}</span><input autoFocus maxLength={120} value={title} onChange={(event) => setTitle(event.target.value)}/></label><button className="p-button-secondary" disabled={busy || !title.trim()}>{t.save}</button><button className="p-button-ghost" type="button" onClick={() => setRename(false)}>{t.cancel}</button></form> : null}
    <details className="argus-owner-menu" onKeyDown={(event) => { if (event.key === 'Escape') { event.currentTarget.open = false; event.currentTarget.querySelector('summary')?.focus(); } }}><summary aria-label={t.conversationMenu}><Ellipsis size={20}/></summary><div role="menu">
      <button type="button" role="menuitem" disabled={busy} onClick={(event) => { const details = event.currentTarget.closest('details'); if (details) details.open = false; setRename(true); }}>{t.rename}</button>
      <button type="button" role="menuitem" disabled={busy} onClick={(event) => { const details = event.currentTarget.closest('details'); if (details) details.open = false; onExport(); }}>{t.legacyExport}</button>
      <button type="button" role="menuitem" disabled={busy} onClick={(event) => apply(event, { pinned: !conversation.pinned })}>{conversation.pinned ? t.unpin : t.pin}</button>
      {conversation.state === 'active' ? <button type="button" role="menuitem" disabled={busy} onClick={(event) => apply(event, { state: 'archived' })}>{t.archive}</button> : <button type="button" role="menuitem" disabled={busy} onClick={(event) => apply(event, { state: 'active' })}>{t.restore}</button>}
      {conversation.state !== 'trashed' ? <button type="button" role="menuitem" disabled={busy} onClick={(event) => apply(event, { state: 'trashed' })}>{t.trash}</button> : null}
    </div></details>
  </div>;
}

function ActiveConversationPage(props: PlatformPageProps) {
  const { locale, currency, query, revision, workspaceKey, onNavigate, onChanged } = props;
  const t = copy(locale);
  const conversationId = query.get('conversation_id') ?? '';
  const stagedDraftId = query.get('draft') ?? '';
  const fromLegacy = query.get('from_legacy') ?? '';
  const newKey = query.get('new') ?? 'new';
  const draftKey = conversationDraftKey(workspaceKey, conversationId || newKey);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [contentScope, setContentScope] = useState('');
  const [busy, setBusy] = useState(false);
  const [ownerBusy, setOwnerBusy] = useState(false);
  const [stage, setStage] = useState<Stage>('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [retryPayload, setRetryPayload] = useState<TurnPayload | null>(null);
  const [atLatest, setAtLatest] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const composerRef = useRef<ArgusComposerHandle>(null);
  const submittedDraftRef = useRef<{ turnId: string; draft: ComposerDraftSnapshot } | null>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const latestRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const controllersRef = useRef(new Set<AbortController>());
  const routeEpochRef = useRef(0);
  const busyRef = useRef(false);
  const scrollAfterSend = useRef(false);
  const sendRef = useRef<(text: string, mentions?: Mention[], draft?: ComposerDraftSnapshot) => Promise<boolean>>(async () => false);
  const routeScope = `${workspaceKey}:${conversationId || newKey}:${stagedDraftId}:${fromLegacy}`;
  const contentCurrent = contentScope === routeScope;
  const visibleDetail = contentCurrent ? detail : null;
  const visibleMessages = contentCurrent ? messages : [];

  const capabilities = useResource(() => request('/chat/capabilities', capabilitiesSchema), [workspaceKey, revision]);
  const context = useResource(() => request('/chat/context', contextSchema), [workspaceKey, revision]);
  const conversation = useResource<ConversationDetail | null>(
    () => conversationId ? request(`/chat/conversations/${encodeURIComponent(conversationId)}?limit=50&offset=0`, conversationDetailSchema) : Promise.resolve(null),
    [workspaceKey, conversationId, revision],
  );

  useEffect(() => {
    routeEpochRef.current += 1;
    abortRef.current?.abort();
    controllersRef.current.forEach((controller) => controller.abort());
    controllersRef.current.clear();
    abortRef.current = null;
    busyRef.current = false;
    setBusy(false);
    setOwnerBusy(false);
    setStage('');
    setError('');
    setNotice('');
    setRetryPayload(null);
    setLoadingOlder(false);
    submittedDraftRef.current = null;
    setDetail(null);
    setMessages([]);
    setContentScope(routeScope);
    return () => {
      routeEpochRef.current += 1;
      abortRef.current?.abort();
      controllersRef.current.forEach((controller) => controller.abort());
      controllersRef.current.clear();
    };
  }, [routeScope]);

  useEffect(() => {
    if (conversation.data) {
      setDetail(conversation.data);
      setMessages(conversation.data.messages);
      setContentScope(routeScope);
    } else if (!conversationId) {
      setDetail(null);
      setMessages([]);
    }
  }, [conversation.data, conversationId, routeScope]);

  const reload = useCallback(() => {
    conversation.reload();
    context.reload();
  }, [conversation, context]);

  const completeTurn = useCallback(async (payload: TurnPayload, addUser: boolean) => {
    if (busyRef.current) return false;
    busyRef.current = true;
    const epoch = routeEpochRef.current;
    const controller = new AbortController();
    abortRef.current = controller;
    controllersRef.current.add(controller);
    setBusy(true);
    setStage(payload.text ? 'interpret' : 'execute');
    setError('');
    setNotice('');
    setRetryPayload(payload);
    if (addUser && payload.text) {
      setMessages((current) => [...current, { id: `local:${payload.turn_id}`, role: 'user', turn_id: payload.turn_id, text: payload.text ?? null, code: 'submitted', cards: [], created_at: new Date().toISOString() }]);
      scrollAfterSend.current = true;
    }
    try {
      const final = await streamTurn(payload, { signal: controller.signal, onStage: (event) => { if (routeEpochRef.current === epoch && event.type === 'stage_start') setStage(event.stage); } });
      if (routeEpochRef.current !== epoch) return false;
      if (final.status === 'model_unavailable') throw new APIError('model_unavailable');
      if (final.status === 'failed') throw new APIError(final.code || 'turn_failed');
      if (final.status === 'in_progress') {
        setNotice(t.inProgress);
      } else if (final.status === 'interrupted') {
        setNotice(t.interrupted);
      } else {
        setRetryPayload(null);
        if (payload.text) {
          const submitted = submittedDraftRef.current;
          const acknowledged = submitted?.turnId === payload.turn_id && composerRef.current?.acknowledge(submitted.draft);
          if (acknowledged) sessionStorage.removeItem(draftKey);
          if (stagedDraftId && acknowledged) clearChatDraft(workspaceKey, stagedDraftId);
          if (submitted?.turnId === payload.turn_id) submittedDraftRef.current = null;
        }
      }
      onChanged();
      if (!conversationId && final.conversation_id) {
        onNavigate('chat', { conversation_id: final.conversation_id, ...(fromLegacy ? { from_legacy: fromLegacy } : {}) });
      } else {
        conversation.reload();
        context.reload();
      }
      return final.status === 'completed';
    } catch (caught) {
      if (routeEpochRef.current !== epoch) return false;
      if (caught instanceof DOMException && caught.name === 'AbortError') setNotice(t.interrupted);
      else setError(errorCopy(caught, locale));
      return false;
    } finally {
      controllersRef.current.delete(controller);
      if (routeEpochRef.current === epoch) {
        busyRef.current = false;
        abortRef.current = null;
        setBusy(false);
        setStage('');
      }
    }
  }, [conversationId, draftKey, fromLegacy, locale, onChanged, onNavigate, stagedDraftId, t.inProgress, t.interrupted, workspaceKey, conversation, context]);

  const sendText = useCallback((text: string, mentions: Mention[] = [], draft?: ComposerDraftSnapshot) => {
    const turnId = stagedChatTurnId(workspaceKey, stagedDraftId, text) ?? crypto.randomUUID();
    const submitted = draft ?? composerRef.current?.snapshot();
    if (submitted) submittedDraftRef.current = { turnId, draft: submitted };
    return completeTurn({
    turn_id: turnId,
    ...(conversationId ? { conversation_id: conversationId } : {}),
    text,
    locale,
    ...turnCurrencyContext(currency),
    mentions: mentions.filter((item) => item.type === 'account' || item.type === 'record').map((item) => ({ kind: item.type as 'account' | 'record', id: item.id, ...(item.type === 'record' && item.provider ? { record_kind: item.provider } : {}) })),
  }, true);
  }, [completeTurn, conversationId, currency, locale, stagedDraftId, workspaceKey]);
  sendRef.current = sendText;

  const sendAction = useCallback((action: PreparedAction) => {
    void completeTurn({ turn_id: crypto.randomUUID(), ...(conversationId ? { conversation_id: conversationId } : {}), action, locale, ...turnCurrencyContext(currency, action) }, false);
  }, [completeTurn, conversationId, currency, locale]);

  useEffect(() => {
    if (!stagedDraftId || capabilities.loading) return;
    const staged = readChatDraft(workspaceKey, stagedDraftId);
    if (!staged || staged.status !== 'ready') return;
    const epoch = routeEpochRef.current;
    const timer = window.setTimeout(() => {
      const submitted = markChatDraftSubmitted(workspaceKey, stagedDraftId);
      if (!submitted || routeEpochRef.current !== epoch) return;
      if (capabilities.data?.model_available === false) setError(t.modelUnavailable);
      else void sendRef.current(composerRef.current?.snapshot().text ?? submitted.text);
    }, 0);
    return () => clearTimeout(timer);
  }, [capabilities.data?.model_available, capabilities.loading, stagedDraftId, t.modelUnavailable, workspaceKey]);

  useEffect(() => {
    const root = transcriptRef.current;
    const target = latestRef.current;
    if (!root || !target) return;
    const observer = new IntersectionObserver(([entry]) => setAtLatest(entry.isIntersecting), { root, threshold: 0.8 });
    observer.observe(target);
    return () => observer.disconnect();
  }, [visibleMessages.length]);
  useEffect(() => {
    if (scrollAfterSend.current || atLatest) latestRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
    scrollAfterSend.current = false;
  }, [visibleMessages.length, busy, atLatest]);

  const discover = useCallback(async (search: string, signal: AbortSignal): Promise<Mention[]> => {
    const data = context.data ?? await request('/chat/context', contextSchema, { signal });
    const phrase = search.toLocaleLowerCase(locale);
    return [
      ...data.accounts.map((account) => ({ id: account.id, type: 'account', label: account.name, insert_text: `@${account.name}`, description: `${account.currency} · ${account.source.title}` })),
      ...data.records.map((record) => ({ id: record.id, type: 'record', label: record.name, insert_text: `@${record.name}`, description: `${record.kind}${record.currency ? ` · ${record.currency}` : ''}`, provider: record.kind })),
    ].filter((item) => !phrase || `${item.label} ${item.description}`.toLocaleLowerCase(locale).includes(phrase)).slice(0, 12);
  }, [context.data, locale]);

  const mutateProposal = async (proposal: Proposal, kind: 'patch' | 'confirm' | 'cancel', changes?: Record<string, string | number | boolean | string[]>) => {
    if (busyRef.current) return false;
    busyRef.current = true;
    const epoch = routeEpochRef.current;
    const controller = new AbortController();
    controllersRef.current.add(controller);
    setBusy(true); setError(''); setNotice('');
    try {
      if (kind === 'patch') await request(`/chat/proposals/${encodeURIComponent(proposal.proposal_id)}`, proposalMutationSchema, { method: 'PATCH', body: JSON.stringify({ expected_revision: proposal.revision, request_id: crypto.randomUUID(), changes }), signal: controller.signal });
      else if (kind === 'confirm') await request(`/chat/proposals/${encodeURIComponent(proposal.proposal_id)}/confirm`, proposalConfirmSchema, { method: 'POST', body: JSON.stringify({ expected_revision: proposal.revision }), signal: controller.signal });
      else await request(`/chat/proposals/${encodeURIComponent(proposal.proposal_id)}/cancel`, proposalMutationSchema, { method: 'POST', body: JSON.stringify({ expected_revision: proposal.revision }), signal: controller.signal });
      if (routeEpochRef.current !== epoch) return false;
      onChanged(); reload();
      return true;
    } catch (caught) {
      if (routeEpochRef.current !== epoch) return false;
      if (caught instanceof APIError && caught.status === 409) { setNotice(t.proposalChanged); reload(); }
      else setError(errorCopy(caught, locale));
      return false;
    } finally {
      controllersRef.current.delete(controller);
      if (routeEpochRef.current === epoch) { busyRef.current = false; setBusy(false); }
    }
  };

  const updateConversation = async (change: { title?: string; pinned?: boolean; state?: ConversationState }) => {
    if (!visibleDetail?.conversation || busyRef.current) return;
    busyRef.current = true;
    const epoch = routeEpochRef.current;
    const controller = new AbortController();
    controllersRef.current.add(controller);
    setOwnerBusy(true); setError('');
    try {
      const next = await request(`/chat/conversations/${encodeURIComponent(visibleDetail.conversation.id)}`, conversationSchema, { method: 'PATCH', body: JSON.stringify(change), signal: controller.signal });
      if (routeEpochRef.current !== epoch) return;
      setDetail((current) => current ? { ...current, conversation: next } : current);
      onChanged();
    } catch (caught) { if (routeEpochRef.current === epoch) setError(errorCopy(caught, locale)); }
    finally {
      controllersRef.current.delete(controller);
      if (routeEpochRef.current === epoch) { busyRef.current = false; setOwnerBusy(false); }
    }
  };
  const exportConversation = async () => {
    if (!visibleDetail?.conversation) return;
    const epoch = routeEpochRef.current;
    const controller = new AbortController();
    controllersRef.current.add(controller);
    setOwnerBusy(true); setError('');
    try {
      const response = await requestResponse(`/chat/conversations/${encodeURIComponent(visibleDetail.conversation.id)}/export`, { signal: controller.signal });
      if (routeEpochRef.current !== epoch) return;
      const url = URL.createObjectURL(await response.blob());
      if (routeEpochRef.current !== epoch) { URL.revokeObjectURL(url); return; }
      const link = document.createElement('a');
      link.href = url;
      link.download = 'argus-conversation.json';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (caught) {
      if (routeEpochRef.current === epoch) setError(caught instanceof APIError && caught.code === 'chat_export_too_large' ? t.exportTooLarge : t.legacyExportError);
    } finally {
      controllersRef.current.delete(controller);
      if (routeEpochRef.current === epoch) setOwnerBusy(false);
    }
  };

  const loadOlder = async () => {
    if (!conversationId || !visibleDetail || visibleMessages.length >= visibleDetail.total) return;
    const epoch = routeEpochRef.current;
    const controller = new AbortController();
    controllersRef.current.add(controller);
    setLoadingOlder(true);
    try {
      const older = await request(`/chat/conversations/${encodeURIComponent(conversationId)}?limit=50&offset=${visibleMessages.length}`, conversationDetailSchema, { signal: controller.signal });
      if (routeEpochRef.current !== epoch) return;
      setMessages((current) => [...older.messages, ...current]);
      setDetail((current) => current ? { ...current, total: older.total } : current);
    } catch (caught) { if (routeEpochRef.current === epoch) setError(errorCopy(caught, locale)); }
    finally {
      controllersRef.current.delete(controller);
      if (routeEpochRef.current === epoch) setLoadingOlder(false);
    }
  };

  const initialDraft = useMemo(() => {
    const staged = readChatDraft(workspaceKey, stagedDraftId);
    if (staged?.status === 'ready') return staged.text;
    return sessionStorage.getItem(draftKey) || staged?.text || '';
  }, [draftKey, stagedDraftId, workspaceKey]);
  const active = !visibleDetail || visibleDetail.conversation.state === 'active';
  const empty = visibleMessages.length === 0 && !conversation.loading;
  const capabilitiesData = capabilities.data;
  const composerSend = (text: string, mentions?: Mention[], draft?: ComposerDraftSnapshot) => {
    if (capabilitiesData?.model_available === false) {
      setError(t.modelUnavailable);
      return false;
    }
    return sendText(text, mentions, draft);
  };

  return <main className="argus-conversation" data-testid="conversation-page">
    <header className="argus-conversation-header">
      <div><p className="p-eyebrow">{t.title}</p><h1 tabIndex={-1}>{visibleDetail?.conversation.title ?? t.newChat}</h1>{visibleDetail?.conversation.pinned ? <span className="argus-pinned"><Pin size={13}/>{t.pin}</span> : null}</div>
      {visibleDetail ? <OwnerMenu conversation={visibleDetail.conversation} locale={locale} busy={ownerBusy || busy} onUpdate={updateConversation} onExport={() => void exportConversation()}/> : null}
    </header>
    {fromLegacy ? <aside className="argus-backlink"><p>{t.legacyBacklink}</p><button type="button" className="p-text-button" onClick={() => onNavigate('chat', { legacy_id: fromLegacy })}>{t.openLegacy}</button></aside> : null}
    <div className="argus-transcript" ref={transcriptRef} tabIndex={-1} data-testid="chat-transcript">
      {visibleDetail && visibleMessages.length < visibleDetail.total ? <button className="argus-load-older" disabled={loadingOlder} type="button" onClick={() => void loadOlder()}>{loadingOlder ? t.loading : t.older}</button> : null}
      {conversation.loading && !visibleDetail ? <p className="p-loading" role="status">{t.loading}</p> : conversation.error ? <div className="p-inline-error" role="alert"><span>{t.loadError}</span><button className="p-button-secondary" onClick={conversation.reload}>{t.retry}</button></div> : null}
      {empty ? <section className="argus-chat-empty"><h2>{t.emptyTitle}</h2><p>{t.emptyBody}</p>{capabilitiesData?.examples.length ? <div className="argus-next-moves" aria-label={t.examples}>{capabilitiesData.examples.map((example) => <button className="argus-next-move" type="button" disabled={busy || ownerBusy} key={example.id} data-example-id={example.id} onClick={() => sendAction(example.action)}><span aria-hidden="true">↳</span>{example.label[locale]}</button>)}</div> : null}</section> : null}
      {visibleMessages.map((message) => <article className={`argus-message argus-message-${message.role}`} key={message.id} data-message-id={message.id} data-turn-id={message.turn_id}>
        {message.text ? <div className="argus-message-copy">{message.text.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div> : null}
        {message.role === 'assistant' ? <div className="argus-message-cards">{message.cards.map((card, index) => <ChatCardView card={card} locale={locale} commands={capabilitiesData?.commands ?? []} calculations={capabilitiesData?.calculations ?? []} busy={busy || ownerBusy} onPatch={(proposal, changes) => mutateProposal(proposal, 'patch', changes)} onConfirm={(proposal) => void mutateProposal(proposal, 'confirm')} onCancel={(proposal) => void mutateProposal(proposal, 'cancel')} onRecompute={sendAction} onNavigate={onNavigate} key={`${card.kind}-${index}`}/>)}</div> : null}
        <footer><time dateTime={message.created_at}>{dateLabel(message.created_at, locale, true)}</time>{message.role === 'assistant' && message.text ? <button type="button" aria-label={locale === 'en' ? 'Copy answer' : 'Copiar respuesta'} onClick={() => void navigator.clipboard.writeText(message.text ?? '')}><Copy size={14}/></button> : null}</footer>
      </article>)}
      {busy ? <div className="argus-turn-status" role="status"><span className="argus-status-dot"/>{stage === 'execute' ? t.executing : t.understanding}<button type="button" className="p-button-ghost" onClick={() => abortRef.current?.abort()}><Square size={13}/>{t.stop}</button></div> : null}
      {notice ? <div className="argus-turn-notice" role="status"><p>{notice}</p><button className="argus-next-move" type="button" disabled={busy} onClick={reload}><RotateCcw size={15}/>{t.reload}</button>{retryPayload ? <button className="argus-next-move" type="button" disabled={busy} onClick={() => void completeTurn(retryPayload, false)}><span aria-hidden="true">↳</span>{t.retry}</button> : null}</div> : null}
      {error ? <div className="argus-turn-error" role="alert"><p>{error}</p>{retryPayload ? <button className="argus-next-move" type="button" disabled={busy} onClick={() => void completeTurn(retryPayload, false)}><RotateCcw size={15}/>{t.retry}</button> : null}</div> : null}
      <div ref={latestRef} className="argus-latest-sentinel" aria-hidden="true"/>
    </div>
    {!atLatest ? <button className="argus-jump-latest" type="button" onClick={() => latestRef.current?.scrollIntoView({ behavior: 'smooth' })}><ArrowDown size={16}/>{t.jumpLatest}</button> : null}
    <footer className="argus-composer-dock">
      {!active ? <p className="argus-honesty">{t.conversationInactive}</p> : null}
      <ArgusComposer ref={composerRef} key={`${draftKey}:${stagedDraftId}`} locale={locale} initialText={initialDraft} disabled={busy || ownerBusy || !active} placeholder={t.composerPlaceholder} onSend={composerSend} onDraftChange={(draft) => { if (draft.text) sessionStorage.setItem(draftKey, draft.text); else sessionStorage.removeItem(draftKey); if (stagedDraftId) updateChatDraftText(workspaceKey, stagedDraftId, draft.text); }} discover={discover} onAttach={() => onNavigate('transactions', { import: '1', from: 'chat', ...(conversationId ? { conversation_id: conversationId } : {}) })} context={capabilitiesData?.model_available === false ? t.freeTextUnavailable : undefined}/>
    </footer>
  </main>;
}

export function ConversationPage(props: PlatformPageProps) {
  const legacyId = props.query.get('legacy_id');
  return legacyId
    ? <LegacyConversation legacyId={legacyId} locale={props.locale} onNavigate={props.onNavigate}/>
    : <ActiveConversationPage {...props}/>;
}
