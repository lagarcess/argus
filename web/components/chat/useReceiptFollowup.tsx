"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import GuestNewConversationDialog from '@/components/guest/GuestNewConversationDialog';
import type { GuestExperience } from '@/components/guest/useGuestExperience';
import type { ProfileState } from './useInitialChatSession';
import type { SendOptions } from './chat-send-selection';
import { clearReceiptFollowup, readReceiptFollowup, runReceiptFork, saveReceiptFollowup, settleReceiptFollowup, bindReceiptFollowupAccount, type ReceiptFollowupIntent } from '@/lib/receipt-followup';
import { getMe, listConversations } from '@/lib/argus-api';
import { newConversationConversionMode } from '@/lib/guest-conversion';

type Options = {
  profileState: ProfileState; account: Awaited<ReturnType<typeof getMe>> | null;
  conversationId: string | null; hydrating: boolean; guest: GuestExperience;
  refreshAccount: () => Promise<Awaited<ReturnType<typeof getMe>> | null>;
  navigate: (id: string, userId?: string) => Promise<void>;
  send: (text: string, options: SendOptions) => Promise<boolean>;
};
export { readReceiptFollowup } from '@/lib/receipt-followup';

type Phase = 'initial' | 'working' | 'choice' | 'conversion' | 'hydrating' | 'error' | 'unavailable' | 'done';

export function useReceiptFollowup(options: Options) {
  const { t } = useTranslation();
  const latest = useRef(options);
  useEffect(() => { latest.current = options; });
  const [intent, setIntent] = useState<ReceiptFollowupIntent | null>(null);
  const [phase, setPhase] = useState<Phase>('initial');
  const [choiceId, setChoiceId] = useState<string | null>(null);
  const busy = useRef(false);
  const conversionSeen = useRef(false);
  const reconciliation = useRef<AbortController | null>(null);
  useEffect(() => { reconciliation.current = new AbortController(); return () => reconciliation.current?.abort(); }, []);
  useEffect(() => { setIntent(readReceiptFollowup()); }, []);
  const cancel = () => { clearReceiptFollowup(); setIntent(null); setPhase('done'); };

  const begin = useCallback(async (replacementId?: string) => {
    if (!intent || busy.current) return;
    busy.current = true;
    setPhase('working');
    try {
      const current = latest.current;
      if (!(await current.guest.admitSend({ text: intent.text, mentions: [], language: intent.language }))) {
        setPhase('error'); return;
      }
      const account = await current.refreshAccount();
      if (!account) throw Error('receipt_account_unavailable');
      // Persist the receiver binding before a request can cross the network.
      const stored = readReceiptFollowup();
      const bound = await bindReceiptFollowupAccount(stored?.requestId === intent.requestId ? stored : intent, account.user.id);
      saveReceiptFollowup(bound);
      setIntent(bound);
      const forked = await runReceiptFork(bound, account.user.id, undefined, replacementId);
      saveReceiptFollowup(forked);
      setIntent(forked);
      await latest.current.navigate(forked.conversationId!, account.user.id);
      setPhase('hydrating');
    } catch (error) {
      const code = (error as { code?: string }).code;
      if (code === 'receipt_guest_choice_required' || code === 'receipt_guest_choice_stale') {
        try {
          const result = await listConversations({ limit: 2 });
          const existingId = result.items[0]?.id ?? null;
          setChoiceId(existingId);
          if (existingId) await latest.current.navigate(existingId);
          setPhase(existingId ? 'choice' : 'error');
        } catch { setPhase('error'); }
      } else setPhase(code === 'receipt_unavailable' ? 'unavailable' : 'error');
    } finally { busy.current = false; }
  }, [intent]);

  useEffect(() => {
    if (!intent || busy.current) return;
    if (phase === 'initial' && ['established', 'bootstrap_required'].includes(options.profileState)) void begin();
    if (phase === 'conversion') {
      if (options.account && options.account.account_kind !== 'guest') void begin();
      else if (options.guest.conversion.isOpen) conversionSeen.current = true;
      else if (conversionSeen.current) { conversionSeen.current = false; setPhase('choice'); }
    }
    if (phase === 'hydrating' && !options.hydrating && options.conversationId === intent.conversationId) {
      busy.current = true;
      void settleReceiptFollowup(intent, {
        send: (text, sendOptions) => latest.current.conversationId === intent.conversationId ? latest.current.send(text, sendOptions) : Promise.resolve(false),
        reconciliation: { signal: reconciliation.current?.signal },
      }).then(async reconciled => {
        if (reconciled) await latest.current.navigate(intent.conversationId!);
        clearReceiptFollowup(intent.requestId); setIntent(null); setPhase('done');
      }).catch(() => setPhase('error')).finally(() => { busy.current = false; });
    }
  }, [intent, phase, options, begin]);

  if (!intent || phase === 'done') return null;
  return <>
    <GuestNewConversationDialog isOpen={phase === 'choice'} isReplacing={false}
      publicAccountAccessEnabled={options.guest.conversion.publicAccountAccessEnabled} onCancel={cancel}
      onStartOver={() => { if (choiceId) void begin(choiceId); }} onConvert={() => {
        // Explicit conversion may move into an existing account. No fork exists yet.
        const unbound = { ...intent }; delete unbound.accountId;
        setIntent(unbound); saveReceiptFollowup(unbound); setPhase('conversion');
        options.guest.conversion.requestConversion('keep_history', null,
          newConversationConversionMode(options.guest.conversion.publicAccountAccessEnabled));
      }} />
    {phase === 'error' || phase === 'unavailable' ? <div role="alert" className="fixed bottom-24 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-3xl -translate-x-1/2 flex-wrap items-center gap-3 rounded-2xl border bg-white px-4 py-3 text-sm dark:bg-neutral-900">
      <p>{t(phase === 'unavailable' ? 'receipt.followup.unavailable' : 'receipt.followup.error')}</p>
      {phase === 'error' ? <button type="button" className="min-h-11 px-3 underline" onClick={() => void begin()}>{t('common.retry', 'Try again')}</button> : null}
      <button type="button" className="min-h-11 px-3" onClick={cancel}>{t('common.cancel', 'Cancel')}</button>
    </div> : null}
  </>;
}
