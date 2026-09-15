"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import ReceiptFollowupBox from './ReceiptFollowupBox';
import { createReceiptFollowup, saveReceiptFollowup } from '@/lib/receipt-followup';
import type { ReceiptCopy } from '@/lib/receipt-copy';

/** Reading this component has no auth, chat or provider side effects. */
export default function ReceiptFollowup({ publicId, copy, language }: { publicId: string; copy: ReceiptCopy; language: string }) {
  const router = useRouter();
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  return <ReceiptFollowupBox copy={copy} value={value} onChange={setValue} disabled={false} busy={busy} onSubmit={event => {
    event.preventDefault();
    if (!value.trim() || busy) return;
    if (!saveReceiptFollowup(createReceiptFollowup(publicId, value, language))) { setFailed(true); return; }
    setBusy(true);
    router.push('/chat');
  }}>{failed ? <p role="alert">{copy.followup.error}</p> : null}</ReceiptFollowupBox>;
}
