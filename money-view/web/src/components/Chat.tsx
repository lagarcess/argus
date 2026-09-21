import { useRef, type FormEvent } from 'react';
import { Bookmark, Check, FileChartColumn, Send } from 'lucide-react';
import type { Example, Home, Locale, PlacementInputs } from '../contracts';
import type { Conversation } from '../useMoneyView';
import { copy, date, errorText, money } from '../i18n';
import { Confirmation } from './Confirmation';

export function Chat({
  home,
  locale,
  conversation,
  draft,
  pending,
  error,
  onDraft,
  onExample,
  onSend,
  onCompute,
  onConfirmationEdit,
  onSave,
}: {
  home: Home;
  locale: Locale;
  conversation: Conversation;
  draft: string;
  pending: string | null;
  error: string | null;
  onDraft: (value: string) => void;
  onExample: (example: Example) => void;
  onSend: () => void;
  onCompute: () => void;
  onConfirmationEdit: (inputs: PlacementInputs) => void;
  onSave: () => void;
}) {
  const t = copy(locale);
  const input = useRef<HTMLTextAreaElement>(null);
  const isSaved =
    conversation.stage === 'result' &&
    home.saved.some((decision) => decision.comparison_id === conversation.result.id);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSend();
  }
  return (
    <aside className="chat-panel" aria-labelledby="chat-title">
      <div className="chat-header">
        <h2 id="chat-title">{t.withClara}</h2>
        <span className="status-dot" aria-hidden="true" />
      </div>
      <div className="chat-thread" aria-live="polite">
        {conversation.stage === 'start' ? (
          <>
            <div className="assistant-message">
              <p>{t.welcome}</p>
            </div>
            <div className="examples">
              <p className="small">{t.demoHelp}</p>
              {home.examples.map((example, index) => (
                <button
                  key={example.id}
                  data-testid={index === 0 ? 'demo-example' : undefined}
                  className="example-button"
                  onClick={() => {
                    onExample(example);
                    input.current?.focus();
                  }}
                >
                  {example.messages[locale]}
                  <span>{t.useExample}</span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <>
            <div className="user-message">
              <p>{conversation.message}</p>
            </div>
            {conversation.stage === 'confirmation' && (
              <Confirmation
                key={conversation.confirmation.id}
                confirmation={conversation.confirmation}
                countries={home.countries}
                locale={locale}
                pending={pending !== null}
                onConfirm={onCompute}
                onInputsChange={onConfirmationEdit}
              />
            )}
            {conversation.stage === 'result' && (
              <>
                <div className="assistant-message">
                  <p>{t.resultReady}</p>
                </div>
                <div className="confirmed-summary">
                  <span className="round-icon">
                    <FileChartColumn size={24} />
                  </span>
                  <div>
                    <strong>
                      {money(
                        conversation.result.inputs.amount,
                        conversation.result.inputs.currency,
                        locale,
                      )}{' '}
                      · {conversation.result.inputs.horizon_days} {t.days}
                    </strong>
                    <p className="small">
                      {t.userSource} · {date(conversation.result.input_source.recorded_on, locale)}
                    </p>
                  </div>
                </div>
                <button
                  className="primary save-button"
                  data-testid="save-comparison"
                  onClick={onSave}
                  disabled={pending !== null || isSaved}
                >
                  {isSaved ? <Check size={18} /> : <Bookmark size={18} />}
                  {isSaved ? t.savedDone : pending === 'save' ? t.working : t.save}
                </button>
                <p className="save-help">
                  <Bookmark size={20} aria-hidden="true" />
                  {t.saveHelp}
                </p>
              </>
            )}
          </>
        )}
        {error && (
          <p className="error" role="alert">
            {error === 'missing_inputs' ? t.missing : errorText(error, t)}
          </p>
        )}
        {pending === 'interpret' && (
          <p className="small" role="status">
            {t.working}
          </p>
        )}
      </div>
      <form className="composer" onSubmit={submit}>
        <label className="sr-only" htmlFor="chat-input">
          {t.placeholder}
        </label>
        <textarea
          ref={input}
          id="chat-input"
          data-testid="chat-input"
          rows={2}
          value={draft}
          placeholder={t.placeholder}
          onChange={(event) => onDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              onSend();
            }
          }}
        />
        <button
          type="submit"
          data-testid="send-message"
          className="send-button"
          aria-label={t.send}
          disabled={!draft.trim() || pending !== null}
        >
          <Send size={20} />
        </button>
      </form>
      <p className="chat-disclosure">{t.disclosure}</p>
    </aside>
  );
}
