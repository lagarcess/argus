import { useState } from 'react';
import { ArrowLeft, ArrowUpRight, Bookmark } from 'lucide-react';
import type { Home, Locale, Notice, SavedDecision, Scenario } from '../contracts';
import type { SavedView } from '../useMoneyView';
import { copy, date, money } from '../i18n';
import { Comparison, type ReceiptSelection } from './Comparison';
import { SourceLink } from './SourceLink';
import { NoticeEvidence } from './NoticeEvidence';
import type { Receipt } from './ReceiptDrawer';

export function Notices({
  notices,
  saved,
  onReceipt,
  locale,
  onOpen,
  pending,
}: {
  notices: Notice[];
  saved: SavedDecision[];
  onReceipt: (receipt: Receipt) => void;
  locale: Locale;
  onOpen: (notice: Notice) => void;
  pending: boolean;
}) {
  const t = copy(locale);
  return (
    <div className="notices">
      {notices.map((notice) => (
        <article key={notice.id} className="notice" data-testid="notice">
          <Bookmark size={20} aria-hidden="true" />
          <div>
            <p>
              {notice.reasons.includes('winner_changed') ? t.leaderChanged : t.inflationChanged}
            </p>
            {notice.reasons.includes('winner_changed') &&
              notice.reasons.includes('inflation_crossed') && <p>{t.inflationChanged}</p>}
            <span className="small">{date(notice.created_at, locale)}</span>
            <NoticeEvidence
              notice={notice}
              original={saved.find((decision) => decision.id === notice.decision_id)?.baseline}
              locale={locale}
              onReceipt={onReceipt}
            />
          </div>
          <button
            data-testid="notice-open"
            className="text-button"
            disabled={pending}
            onClick={() => onOpen(notice)}
          >
            {t.beforeAfter}
            <ArrowUpRight size={15} aria-hidden="true" />
          </button>
        </article>
      ))}
    </div>
  );
}
export function SavedList({
  home,
  locale,
  onOpen,
  onReceipt,
  pending,
}: {
  home: Home;
  locale: Locale;
  onOpen: (id: string) => void;
  onReceipt: (selection: ReceiptSelection) => void;
  pending: boolean;
}) {
  const t = copy(locale);
  if (!home.saved.length)
    return (
      <div className="empty-saved">
        <Bookmark size={32} />
        <h2>{t.noSaved}</h2>
        <p>{t.noSavedBody}</p>
      </div>
    );
  return (
    <div className="saved-list">
      {home.saved.map((decision) => (
        <article key={decision.id} className="saved-row">
          <div>
            <h2>
              {money(decision.baseline.inputs.amount, decision.baseline.inputs.currency, locale)} ·{' '}
              {decision.baseline.inputs.horizon_days} {t.days}
            </h2>
            <p className="small">
              {t.savedOn} {date(decision.created_at, locale)}
            </p>
            <SourceLink
              source={decision.baseline.input_source}
              locale={locale}
              onOpen={() => {
                const row = decision.baseline.rows[0];
                if (row) onReceipt({ kind: 'result', result: decision.baseline, row });
              }}
            />
          </div>
          <button className="text-button" onClick={() => onOpen(decision.id)} disabled={pending}>
            {t.openSaved}
            <ArrowUpRight size={18} aria-hidden="true" />
          </button>
        </article>
      ))}
    </div>
  );
}
export function SavedDetail({
  view,
  locale,
  onBack,
  onReceipt,
}: {
  view: SavedView;
  locale: Locale;
  onBack: () => void;
  onReceipt: (selection: Receipt) => void;
}) {
  const t = copy(locale);
  const [period, setPeriod] = useState<'before' | 'after'>('after');
  const before = view.notice?.before ?? view.decision.baseline;
  const after = view.notice?.after ?? view.decision.latest;
  const lastCheck = view.decision.checks.at(-1);
  return (
    <section data-testid="saved-detail" className="saved-detail">
      <button className="text-button back-button" onClick={onBack}>
        <ArrowLeft size={16} />
        {t.back}
      </button>
      <h2>{view.notice ? t.beforeAfter : t.history}</h2>
      {lastCheck?.status === 'failed' && (
        <div className="source-status warning" role="status" data-testid="saved-check-failed">
          <p>{t.latestCheckFailed}</p>
          <span className="small">
            {t.checkAttempt} {date(lastCheck.created_at, locale)}
          </span>
        </div>
      )}
      {view.notice && (
        <NoticeEvidence
          notice={view.notice}
          original={view.decision.baseline}
          locale={locale}
          onReceipt={onReceipt}
        />
      )}
      <div className="period-tabs" aria-label={t.beforeAfter}>
        <button aria-pressed={period === 'before'} onClick={() => setPeriod('before')}>
          {view.notice ? t.before : t.original}
          <span>{date(before.created_at, locale)}</span>
        </button>
        <button aria-pressed={period === 'after'} onClick={() => setPeriod('after')}>
          {view.notice ? t.after : t.latest}
          <span>{date(after.created_at, locale)}</span>
        </button>
      </div>
      <Comparison
        result={period === 'before' ? before : after}
        locale={locale}
        onReceipt={onReceipt}
      />
    </section>
  );
}
const scenarios: Scenario[] = ['same_winner', 'leader_changed', 'inflation_crossed', 'failure'];
export function DemoControls({
  locale,
  loading,
  onSimulate,
}: {
  locale: Locale;
  loading: boolean;
  onSimulate: (scenario: Scenario) => void;
}) {
  const t = copy(locale);
  const [scenario, setScenario] = useState<Scenario>('leader_changed');
  return (
    <section className="demo-controls" aria-labelledby="demo-title">
      <h3 id="demo-title">{t.demoControls}</h3>
      <div>
        <label>
          {t.scenario}
          <select
            data-testid="demo-scenario"
            value={scenario}
            disabled={loading}
            onChange={(event) => {
              const selected = scenarios.find((item) => item === event.target.value);
              if (selected) setScenario(selected);
            }}
          >
            {scenarios.map((item) => (
              <option key={item} value={item}>
                {t[item]}
              </option>
            ))}
          </select>
        </label>
        <button
          className="secondary"
          data-testid="publish-demo-event"
          disabled={loading}
          onClick={() => onSimulate(scenario)}
        >
          {loading ? t.working : t.simulate}
        </button>
      </div>
    </section>
  );
}
