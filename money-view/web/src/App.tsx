import { useEffect, useState } from 'react';
import { Pencil, RefreshCw } from 'lucide-react';
import { copy, date, errorText, initialLocale, money } from './i18n';
import type { Locale } from './contracts';
import { useMoneyView } from './useMoneyView';
import { Chat } from './components/Chat';
import { Comparison } from './components/Comparison';
import { DemoControls, Notices, SavedDetail, SavedList } from './components/Saved';
import { ReceiptDrawer, type Receipt } from './components/ReceiptDrawer';
import { SourceLink } from './components/SourceLink';

export default function App() {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const view = useMoneyView(locale);
  const t = copy(locale);
  const home = view.home;
  const example = home?.examples[0];
  const result = view.conversation.stage === 'result' ? view.conversation.result : null;
  const amountInputs = result?.inputs ?? example?.inputs;
  const formattedAmount = amountInputs
    ? money(amountInputs.amount, amountInputs.currency, locale)
    : '';
  useEffect(() => {
    document.documentElement.lang = locale;
    try {
      localStorage.setItem('clara-locale', locale);
    } catch {
      /* Locale remains usable without storage. */
    }
  }, [locale]);
  function beginExample() {
    if (example) {
      view.chooseExample(example);
      document.getElementById('chat-input')?.focus();
    }
  }
  return (
    <>
      <header className="site-header">
        <a className="wordmark" href="#money" onClick={() => view.setPage('money')}>
          Clara
        </a>
        <nav aria-label={locale === 'en' ? 'Main navigation' : 'Navegación principal'}>
          <button
            aria-current={view.page === 'money' ? 'page' : undefined}
            onClick={() => view.setPage('money')}
          >
            {t.money}
          </button>
          <button
            aria-current={view.page === 'saved' ? 'page' : undefined}
            onClick={() => {
              view.setPage('saved');
              view.setSavedView(null);
            }}
          >
            {t.saved}
            {home && home.saved.length > 0 && (
              <span className="nav-count">{home.saved.length}</span>
            )}
          </button>
        </nav>
        <div className="language-controls" aria-label="Language / Idioma">
          <button
            data-testid="lang-es"
            aria-label="Español"
            aria-pressed={locale === 'es-419'}
            onClick={() => setLocale('es-419')}
          >
            ES
          </button>
          <span>/</span>
          <button
            data-testid="lang-en"
            aria-label="English"
            aria-pressed={locale === 'en'}
            onClick={() => setLocale('en')}
          >
            EN
          </button>
        </div>
      </header>
      {!home ? (
        <main className="initial-state" aria-live="polite">
          <h1 className="display">{t.headline}</h1>
          <p>{view.homeError ? errorText(view.homeError, t) : t.loading}</p>
          {view.homeError && (
            <button
              className="secondary"
              onClick={() => {
                void view.refresh();
              }}
            >
              <RefreshCw size={16} />
              {t.retry}
            </button>
          )}
        </main>
      ) : (
        <>
          <main className="money-layout" id="money">
            <div className="money-column">
              <h1 className="display">{view.page === 'money' ? t.headline : t.saved}</h1>
              {view.page === 'money' ? (
                <>
                  {(result || example) && (
                    <div className="balance-section">
                      <button
                        className="balance"
                        onClick={beginExample}
                        aria-label={`${t.amount}: ${formattedAmount}. ${t.confirmHelp}`}
                      >
                        <span>{formattedAmount}</span>
                        <Pencil size={19} aria-hidden="true" />
                      </button>
                      {result ? (
                        <SourceLink
                          source={result.input_source}
                          locale={locale}
                          onOpen={() => {
                            const row = result.rows[0];
                            if (row) setReceipt({ kind: 'result', result, row });
                          }}
                        />
                      ) : (
                        example && (
                          <button
                            className="source-link"
                            onClick={() => setReceipt({ kind: 'source', source: example.source })}
                          >
                            {t.sample} · {t.syntheticSource} ·{' '}
                            {date(example.source.published_on, locale)}
                          </button>
                        )
                      )}
                    </div>
                  )}
                  {result ? (
                    <Comparison result={result} locale={locale} onReceipt={setReceipt} />
                  ) : (
                    <section className="empty-comparison">
                      <span className="quiet-rule" />
                      <h2>{t.emptyTitle}</h2>
                      <p>{t.emptyBody}</p>
                      <button className="text-button" onClick={beginExample}>
                        {t.emptyAction}
                      </button>
                    </section>
                  )}
                </>
              ) : view.savedView ? (
                <SavedDetail
                  key={`${view.savedView.decision.id}-${view.savedView.notice?.id ?? 'latest'}`}
                  view={view.savedView}
                  locale={locale}
                  onBack={() => view.setSavedView(null)}
                  onReceipt={setReceipt}
                />
              ) : (
                <SavedList
                  home={home}
                  locale={locale}
                  onOpen={(id) => {
                    void view.openDecision(id);
                  }}
                  onReceipt={setReceipt}
                  pending={view.pending !== null}
                />
              )}
              {(view.loadingSources ||
                home.source_status.state === 'stale' ||
                home.source_status.state === 'unavailable' ||
                (home.source_status.state === 'ready' && home.saved.length > 0)) && (
                <div
                  className={`source-status ${home.source_status.state === 'stale' ? 'warning' : ''}`}
                  role="status"
                >
                  <p>
                    {view.loadingSources
                      ? t.loadingSources
                      : home.source_status.state === 'stale'
                        ? t.stale
                        : home.source_status.state === 'ready'
                          ? t.readySources
                          : t.unavailable}
                  </p>
                  {home.source_status.last_success_at && (
                    <span className="small">
                      {t.lastGood} · {date(home.source_status.last_success_at, locale)}
                    </span>
                  )}
                </div>
              )}
              {view.homeError && (
                <p className="error" role="alert">
                  {errorText(view.homeError, t)}
                </p>
              )}
              <Notices
                notices={home.notices}
                saved={home.saved}
                onReceipt={setReceipt}
                locale={locale}
                onOpen={(notice) => {
                  void view.openDecision(notice.decision_id, notice);
                }}
                pending={view.pending !== null}
              />
              {home.demo && home.saved.length > 0 && (
                <DemoControls
                  locale={locale}
                  loading={view.loadingSources || view.pending !== null}
                  onSimulate={(scenario) => {
                    void view.simulate(scenario);
                  }}
                />
              )}
            </div>
            <Chat
              home={home}
              locale={locale}
              conversation={view.conversation}
              draft={view.draft}
              pending={view.pending}
              error={view.error}
              onDraft={view.editDraft}
              onExample={view.chooseExample}
              onSend={() => {
                void view.send();
              }}
              onCompute={(inputs) => {
                void view.compute(inputs);
              }}
              onSave={() => {
                void view.save();
              }}
            />
          </main>
          <footer className="site-footer">{t.disclosure}</footer>
        </>
      )}
      {receipt && (
        <ReceiptDrawer receipt={receipt} locale={locale} onClose={() => setReceipt(null)} />
      )}
    </>
  );
}
