import { describe, test, expect } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { I18nextProvider } from 'react-i18next';
import { createInstance } from 'i18next';
import ChatMessage from '../components/chat/ChatMessage';
import { hydrateMessagesFromApi } from '../components/chat/chat-message-projection';
import { backtestTurn, researchTurn, legacyReceipt } from './fixtures/receipt-turns';
import calculationFixture from './fixtures/calculation-cards.json';
import type { PublicReceiptTurn } from '../lib/public-receipt-turns';
import type { ApiMessage } from '../lib/argus-api';
import { normalizeEnabledLanguage } from '../lib/language-features';
import en from '../public/locales/en/common.json';
import es from '../public/locales/es-419/common.json';

const calculationTurn = calculationFixture.receipt_turn as PublicReceiptTurn;
const answerTurn: PublicReceiptTurn = { kind: 'answer', question: 'What does saving mean?', answer: 'Saving sets money aside.', content_language: 'en', provenance_mark: 'tested_with_argus', framing: 'answer_not_advice' };

describe.each(['en', 'es-419'] as const)('carried messages in %s', language => {
  test.each([backtestTurn, researchTurn, calculationTurn, answerTurn, legacyReceipt])('renders frozen %s without live actions or appended history facts', async card => {
    const i18n = createInstance();
    await i18n.init({ lng: language, resources: { en: { translation: en }, 'es-419': { translation: es } } });
    const source = { id: 'imported', role: 'assistant', content: 'hidden-history-json-facts', metadata: {
      shared_conversation: { snapshot_at: '2026-09-14T20:30:00Z', card },
      // Provenance owns the projection even if unrelated legacy metadata is present.
      result_run_id: 'private-run', confirmation_card: {}, memory_recalls: [{ text: 'private-memory' }],
    } } as unknown as ApiMessage;
    const message = hydrateMessagesFromApi([source]).messages[0];
    expect(message.sharedConversation).toBeDefined();
    expect(message.result).toBeUndefined();
    expect(message.confirmation).toBeUndefined();
    expect(message.computation).toBeUndefined();
    expect(message.memoryRecalls).toBeUndefined();
    const html = renderToStaticMarkup(<I18nextProvider i18n={i18n}><ChatMessage message={message} conversationId="receiver" isLatest /></I18nextProvider>);
    expect(html).not.toContain('hidden-history-json-facts');
    expect(html).not.toContain('private-run');
    expect(html).not.toContain('private-memory');
    expect(html).not.toContain('<input');
    expect(html).not.toContain('contenteditable');
    expect(html).toContain('2026');
    expect(html).toContain(normalizeEnabledLanguage(language) === 'en' ? 'From a shared conversation' : 'conversación compartida');
  });
});
