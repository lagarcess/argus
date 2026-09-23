import { useState } from 'react';
import { FileUp, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { request } from '../../platform/client';
import { useRecordFocus } from '../../argus/useRecordFocus';
import { useResource } from '../../platform/hooks';
import type { PlatformPageProps } from '../../platform/types';
import { EmptyState, EvidenceLine, Modal, Money, PageHeader, Panel } from '../../platform/ui';
import { copy, dateLabel, exactCurrencyLabel, percentLabel } from './copy';
import {
  bundleListSchema,
  deletedSchema,
  investingWorkspaceSchema,
  planListSchema,
  planRunSchema,
  planSchema,
  portfolioSchema,
  priceLoadSchema,
  type Benchmark,
  type Bundle,
  type Holding,
  type InvestingWorkspace,
  type OrderReceipt,
  type RecurringPlan,
} from './contracts';
import { CsvImportDialog, HoldingDialog, messageFor, OrderDialog, PlanDialog } from './dialogs';
import './investing.css';

function quantityLabel(value: string, locale: PlatformPageProps['locale']) {
  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat(locale, { maximumFractionDigits: 8 }).format(number)
    : value;
}

function SignedPercent({ value, locale }: { value: string | null; locale: PlatformPageProps['locale'] }) {
  const label = percentLabel(value, locale);
  if (!label) return <span>{copy(locale).unavailable}</span>;
  const numeric = Number(value);
  return <span>{numeric > 0 ? '+' : ''}{label}</span>;
}

function BenchmarkChart({ benchmark, locale }: { benchmark: Benchmark; locale: PlatformPageProps['locale'] }) {
  const t = copy(locale);
  const start = Number(benchmark.start_price);
  const end = Number(benchmark.end_price);
  const valid = Number.isFinite(start) && Number.isFinite(end);
  const low = valid ? Math.min(start, end) : 0;
  const high = valid ? Math.max(start, end) : 0;
  const range = high - low || 1;
  const y = (value: number) => 70 - ((value - low) / range) * 44;
  return (
    <div className="investing-benchmark">
      <div className="investing-benchmark-heading">
        <div><strong>{benchmark.symbol}</strong><span>{benchmark.name}</span></div>
        <strong className="investing-return"><SignedPercent value={benchmark.return_pct} locale={locale} /></strong>
      </div>
      {valid ? (
        <svg viewBox="0 0 280 96" role="img" aria-labelledby={`chart-${benchmark.id}`}>
          <title id={`chart-${benchmark.id}`}>{t.performanceChart}: {benchmark.symbol}, {t.start} {benchmark.start_price} {benchmark.currency}, {t.end} {benchmark.end_price} {benchmark.currency}</title>
          <desc>{t.chartDescription}</desc>
          <line x1="28" y1="82" x2="252" y2="82" className="investing-axis" />
          <path d={`M 34 ${y(start)} L 246 ${y(end)}`} className="investing-line" />
          <circle cx="34" cy={y(start)} r="5" className="investing-point" />
          <circle cx="246" cy={y(end)} r="5" className="investing-point" />
        </svg>
      ) : null}
      <div className="p-table-wrap">
        <table className="p-table investing-chart-table">
          <caption className="sr-only">{t.chartDescription}</caption>
          <thead><tr><th>{t.date}</th><th>{t.price}</th></tr></thead>
          <tbody>
            <tr><td>{dateLabel(benchmark.start_on, locale)}</td><td><Money amount={benchmark.start_price} currency={benchmark.currency} locale={locale} /></td></tr>
            <tr><td>{dateLabel(benchmark.end_on, locale)}</td><td><Money amount={benchmark.end_price} currency={benchmark.currency} locale={locale} /></td></tr>
          </tbody>
        </table>
      </div>
      <EvidenceLine evidence={benchmark.source} locale={locale} />
    </div>
  );
}

function PortfolioView({
  workspace,
  locale,
  focusCurrency,
  pending,
  onAdd,
  onEdit,
  onRemove,
  onImport,
  onRefreshPrices,
}: {
  workspace: InvestingWorkspace;
  locale: PlatformPageProps['locale'];
  focusCurrency?: string;
  pending: boolean;
  onAdd: () => void;
  onEdit: (holding: Holding) => void;
  onRemove: (holding: Holding) => void;
  onImport: () => void;
  onRefreshPrices: () => void;
}) {
  const t = copy(locale);
  const { portfolio } = workspace;
  const totals = [...portfolio.totals].sort((a, b) => Number(b.currency === focusCurrency) - Number(a.currency === focusCurrency));
  return (
    <div className="investing-sections">
      <Panel className="investing-summary" aria-labelledby="investing-summary-title">
        <div className="investing-section-header"><div><h2 id="investing-summary-title">{t.summary}</h2><p className="p-muted">{t.asOf} {dateLabel(portfolio.as_of, locale)}</p></div></div>
        {totals.length > 0 ? <div className="investing-currency-groups">{totals.map(total => <article className={`investing-currency${total.currency === focusCurrency ? ' is-focused' : ''}`} key={total.currency}>
          <div className="investing-currency-title"><h3>{total.currency}</h3>{total.is_partial ? <span className="p-badge">{t.partial}</span> : null}</div>
          <div className="p-metrics investing-metrics">
            <div className="p-metric investing-primary-metric"><span>{t.value}</span><strong><Money amount={total.portfolio_value} currency={total.currency} locale={locale} /></strong></div>
            <div className="p-metric"><span>{t.linkedValue}</span><strong><Money amount={total.linked_accounts} currency={total.currency} locale={locale} /></strong></div>
            <div className="p-metric"><span>{t.alternativeValue}</span><strong><Money amount={total.priced_alternatives} currency={total.currency} locale={locale} /></strong></div>
            <div className="p-metric"><span>{t.cost}</span><strong><Money amount={total.alternative_cost_basis} currency={total.currency} locale={locale} /></strong></div>
            <div className="p-metric"><span>{t.gainLoss}</span><strong><Money amount={total.alternative_gain_loss} currency={total.currency} locale={locale} /> <small><SignedPercent value={total.alternative_gain_loss_pct} locale={locale} /></small></strong></div>
          </div>
          <EvidenceLine evidence={total.source} locale={locale} />
        </article>)}</div> : <EmptyState title={t.noLinked} />}
      </Panel>

      <Panel aria-labelledby="linked-title">
        <div className="investing-section-header"><div><h2 id="linked-title">{t.linkedAccounts}</h2><p className="p-muted">{t.linkedIntro}</p></div></div>
        {portfolio.linked_accounts.length > 0 ? <div className="p-ledger">{portfolio.linked_accounts.map(account => <article className="p-ledger-row" key={account.id} data-record-id={account.id} tabIndex={-1}>
          <div className="p-row-main"><strong>{account.name}</strong><EvidenceLine evidence={account.source} locale={locale} /></div>
          <div className="p-row-value"><strong><Money amount={account.balance} currency={account.currency} locale={locale} /></strong><span className="p-muted">{account.currency}</span></div>
        </article>)}</div> : <EmptyState title={t.noLinked} />}
      </Panel>

      <Panel aria-labelledby="alternatives-title">
        <div className="investing-section-header">
          <div><h2 id="alternatives-title">{t.alternatives}</h2><p className="p-muted">{t.alternativesIntro}</p></div>
          <div className="p-actions">
            <a className="p-button-ghost" href="/api/platform/investing/holdings/sample.csv" download>{t.sampleCsv}</a>
            <button className="p-button-secondary" onClick={onImport}><FileUp size={16} />{t.importCsv}</button>
            <button className="p-button" onClick={onAdd}><Plus size={16} />{t.addHolding}</button>
          </div>
        </div>
        {portfolio.alternative_holdings.length > 0 ? <div className="p-ledger investing-holdings">{portfolio.alternative_holdings.map(holding => {
          const allocation = Math.max(0, Math.min(100, Number(holding.allocation_pct ?? 0)));
          return <article className="p-ledger-row investing-holding" key={holding.id} data-record-id={holding.id} tabIndex={-1}>
            <div className="p-row-main">
              <div className="investing-holding-name"><strong>{holding.name}</strong><span>{holding.symbol} · {quantityLabel(holding.quantity, locale)} {t.quantity.toLowerCase()}</span></div>
              <div className="investing-allocation" aria-label={`${t.allocation}: ${percentLabel(holding.allocation_pct, locale) ?? t.unavailable}`}><span style={{ width: `${allocation}%` }} /></div>
              <EvidenceLine evidence={holding.source} locale={locale} />
            </div>
            <div className="investing-holding-values">
              <dl><div><dt>{t.cost}</dt><dd><Money amount={holding.total_cost} currency={holding.currency} locale={locale} /></dd></div><div><dt>{t.marketValue}</dt><dd>{holding.market_value === null ? t.unavailable : <Money amount={holding.market_value} currency={holding.currency} locale={locale} />}</dd></div><div><dt>{t.gainLoss}</dt><dd>{holding.gain_loss === null ? t.unavailable : <><Money amount={holding.gain_loss} currency={holding.currency} locale={locale} /> <small><SignedPercent value={holding.gain_loss_pct} locale={locale} /></small></>}</dd></div></dl>
              <div className="p-row-actions"><button className="p-icon-button" aria-label={`${t.edit}: ${holding.name}`} onClick={() => onEdit(holding)}><Pencil size={17} /></button><button className="p-icon-button" aria-label={`${t.remove}: ${holding.name}`} onClick={() => onRemove(holding)}><Trash2 size={17} /></button></div>
            </div>
          </article>;
        })}</div> : <EmptyState title={t.noAlternatives} description={t.noAlternativesHelp} action={<button className="p-button" onClick={onAdd}>{t.addHolding}</button>} />}
        <div className="investing-refresh"><button className="p-button-ghost" disabled={pending} onClick={onRefreshPrices}><RefreshCw size={16} />{pending ? t.refreshing : t.refreshPrices}</button><EvidenceLine evidence={portfolio.source} locale={locale} /></div>
      </Panel>

      <Panel aria-labelledby="benchmarks-title">
        <div className="investing-section-header"><div><h2 id="benchmarks-title">{t.benchmarks}</h2><p className="p-muted">{t.benchmarkIntro}</p></div></div>
        <div className="investing-benchmarks">{portfolio.benchmarks.map(item => <BenchmarkChart key={item.id} benchmark={item} locale={locale} />)}</div>
      </Panel>
    </div>
  );
}

function ReceiptRow({ receipt, locale }: { receipt: OrderReceipt; locale: PlatformPageProps['locale'] }) {
  const t = copy(locale);
  return <article className="p-ledger-row" data-record-id={receipt.id} tabIndex={-1}><div className="p-row-main"><strong>{receipt.side === 'buy' ? t.buy : t.sell} · {receipt.symbol ?? receipt.bundle_id}</strong><span>{dateLabel(receipt.confirmed_at, locale)}</span><EvidenceLine evidence={receipt.source} locale={locale} /></div><div className="p-row-value"><strong><Money amount={receipt.gross} currency={receipt.currency} locale={locale} /></strong><span>{t.roundingCost}: <data value={receipt.rounding_cost}>{exactCurrencyLabel(receipt.rounding_cost, receipt.currency)}</data></span><span>{t.cashAfter}: <Money amount={receipt.cash_after} currency={receipt.currency} locale={locale} /></span></div></article>;
}

function SimulationView({
  workspace,
  locale,
  pendingPlanId,
  onOrder,
  onBundle,
  onPlan,
  onTogglePlan,
  onRunPlan,
}: {
  workspace: InvestingWorkspace;
  locale: PlatformPageProps['locale'];
  pendingPlanId: string | null;
  onOrder: () => void;
  onBundle: (bundle: Bundle) => void;
  onPlan: () => void;
  onTogglePlan: (plan: RecurringPlan) => void;
  onRunPlan: (plan: RecurringPlan) => void;
}) {
  const t = copy(locale);
  const { portfolio } = workspace;
  return <div className="investing-sections">
    <div className="investing-boundary" role="note"><strong>{t.simulation}</strong><span>{t.simulatedBoundary}</span><button className="p-button" onClick={onOrder}>{t.simulateChange}</button></div>
    <Panel aria-labelledby="cash-title"><div className="investing-section-header"><div><h2 id="cash-title">{t.fictionalCash}</h2><p className="p-muted">{t.simulatedBoundary}</p></div></div>{portfolio.simulation.books.length > 0 ? <div className="p-ledger">{portfolio.simulation.books.map(book => <article className="p-ledger-row" key={book.id} data-record-id={book.id} tabIndex={-1}><div className="p-row-main"><strong>{book.name}</strong><EvidenceLine evidence={book.source} locale={locale} /></div><div className="investing-book-values"><span><small>{t.fictionalCash}</small><strong><Money amount={book.cash} currency={book.currency} locale={locale} /></strong></span><span><small>{t.initialCash}</small><strong><Money amount={book.initial_cash} currency={book.currency} locale={locale} /></strong></span></div></article>)}</div> : <EmptyState title={t.unavailable} />}</Panel>
    <Panel aria-labelledby="positions-title"><div className="investing-section-header"><div><h2 id="positions-title">{t.practicePositions}</h2></div></div>{portfolio.simulation.positions.length > 0 ? <div className="p-ledger">{portfolio.simulation.positions.map(position => <article className="p-ledger-row" key={`${position.book_id}-${position.symbol}`}><div className="p-row-main"><strong>{position.symbol}</strong><span>{quantityLabel(position.quantity, locale)} {t.quantity.toLowerCase()}</span><EvidenceLine evidence={position.source} locale={locale} /></div><div className="investing-holding-values"><dl><div><dt>{t.cost}</dt><dd><Money amount={position.total_cost} currency={position.currency} locale={locale} /></dd></div><div><dt>{t.marketValue}</dt><dd>{position.market_value === null ? t.unavailable : <Money amount={position.market_value} currency={position.currency} locale={locale} />}</dd></div><div><dt>{t.gainLoss}</dt><dd>{position.gain_loss === null ? t.unavailable : <><Money amount={position.gain_loss} currency={position.currency} locale={locale} /> <small><SignedPercent value={position.gain_loss_pct} locale={locale} /></small></>}</dd></div></dl></div></article>)}</div> : <EmptyState title={t.noPositions} action={<button className="p-button" onClick={onOrder}>{t.simulateChange}</button>} />}</Panel>
    <Panel aria-labelledby="bundles-title"><div className="investing-section-header"><div><h2 id="bundles-title">{t.bundles}</h2><p className="p-muted">{t.bundleIntro}</p></div></div><div className="investing-bundle-grid">{workspace.bundles.map(bundle => <article className="investing-bundle" key={bundle.id}><div><h3>{bundle.name}</h3><p>{bundle.description}</p></div><ul>{bundle.legs.map(leg => <li key={leg.symbol}><strong>{leg.symbol}</strong><span>{percentLabel(leg.weight_pct, locale)} {t.weight}</span></li>)}</ul><EvidenceLine evidence={bundle.source} locale={locale} /><button className="p-button-secondary" onClick={() => onBundle(bundle)}>{t.useBundle}</button></article>)}</div></Panel>
    <Panel aria-labelledby="recurring-title"><div className="investing-section-header"><div><h2 id="recurring-title">{t.recurring}</h2><p className="p-muted">{t.recurringIntro}</p></div><button className="p-button" onClick={onPlan}><Plus size={16} />{t.createPlan}</button></div>{workspace.plans.length > 0 ? <div className="p-ledger">{workspace.plans.map(plan => <article className="p-ledger-row" key={plan.id} data-record-id={plan.id} tabIndex={-1}><div className="p-row-main"><strong>{plan.symbol ?? plan.bundle_id}</strong><span>{plan.cadence === 'weekly' ? t.weekly : t.monthly} · {t.nextRun}: {dateLabel(plan.next_run_on, locale)}</span><EvidenceLine evidence={plan.source} locale={locale} /></div><div className="p-row-value"><strong><Money amount={plan.amount} currency={plan.currency} locale={locale} /></strong><span>{plan.active ? t.active : t.paused}</span><div className="p-row-actions"><button className="p-button-ghost" disabled={pendingPlanId === plan.id} onClick={() => onTogglePlan(plan)}>{plan.active ? t.pause : t.resume}</button><button className="p-button-secondary" disabled={!plan.active || pendingPlanId === plan.id} onClick={() => onRunPlan(plan)}>{pendingPlanId === plan.id ? t.running : t.runPeriod}</button></div></div></article>)}</div> : <EmptyState title={t.noPlans} action={<button className="p-button" onClick={onPlan}>{t.createPlan}</button>} />}</Panel>
    <Panel aria-labelledby="orders-title"><div className="investing-section-header"><div><h2 id="orders-title">{t.recentOrders}</h2></div></div>{portfolio.simulation.recent_orders.length > 0 ? <div className="p-ledger">{portfolio.simulation.recent_orders.map(receipt => <ReceiptRow key={receipt.id} receipt={receipt} locale={locale} />)}</div> : <EmptyState title={t.noOrders} />}</Panel>
  </div>;
}

export function InvestmentsPage(props: PlatformPageProps) {
  const { locale, currency, query, revision, onNavigate, onChanged } = props;
  const t = copy(locale);
  const focusCurrency = query.get('currency')?.toUpperCase();
  const targetId = query.get('record_id') ?? query.get('account_id');
  const resource = useResource(async () => {
    const [portfolio, bundles, plans] = await Promise.all([
      request('/investing/portfolio', portfolioSchema),
      request('/investing/bundles', bundleListSchema),
      request('/investing/recurring-plans', planListSchema),
    ]);
    return investingWorkspaceSchema.parse({ portfolio, bundles: bundles.items, plans: plans.items });
  }, [locale, currency, query.toString(), revision]);
  const simulationRecords = resource.data ? [...resource.data.portfolio.simulation.books, ...resource.data.portfolio.simulation.recent_orders, ...resource.data.plans] : [];
  const targetIsSimulation = simulationRecords.some(record => record.id === targetId);
  const activeTab = query.get('tab') === 'simulation' || (!query.has('tab') && targetIsSimulation) ? 'simulation' : 'portfolio';
  const recordRef = useRecordFocus<HTMLElement>(targetId, [resource.data, activeTab]);
  const [holdingDialog, setHoldingDialog] = useState<Holding | 'new' | null>(null);
  const [removeHolding, setRemoveHolding] = useState<Holding | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [showOrder, setShowOrder] = useState(false);
  const [selectedBundle, setSelectedBundle] = useState<string | undefined>();
  const [showPlan, setShowPlan] = useState(false);
  const [pending, setPending] = useState(false);
  const [pendingPlanId, setPendingPlanId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [status, setStatus] = useState<string | null>(null);
  function changed(message = t.saved) {
    setStatus(message);
    resource.reload();
    onChanged();
  }
  async function remove() {
    if (!removeHolding) return;
    setPending(true); setActionError(null); setStatus(null);
    try {
      await request(`/investing/holdings/${encodeURIComponent(removeHolding.id)}`, deletedSchema, { method: 'DELETE' });
      setRemoveHolding(null); changed();
    } catch (caught) { setActionError(caught); }
    finally { setPending(false); }
  }
  async function refreshPrices() {
    setPending(true); setActionError(null); setStatus(null);
    try {
      await request('/investing/prices/load', priceLoadSchema, { method: 'POST', body: JSON.stringify({ outcome: 'success' }) });
      changed();
    } catch (caught) { setActionError(caught); }
    finally { setPending(false); }
  }
  async function togglePlan(plan: RecurringPlan) {
    setPendingPlanId(plan.id); setActionError(null); setStatus(null);
    try {
      await request(`/investing/recurring-plans/${encodeURIComponent(plan.id)}`, planSchema, { method: 'PATCH', body: JSON.stringify({ active: !plan.active }) });
      changed();
    } catch (caught) { setActionError(caught); }
    finally { setPendingPlanId(null); }
  }
  async function runPlan(plan: RecurringPlan) {
    if (!resource.data) return;
    setPendingPlanId(plan.id); setActionError(null); setStatus(null);
    try {
      await request(`/investing/recurring-plans/${encodeURIComponent(plan.id)}/run`, planRunSchema, { method: 'POST', body: JSON.stringify({ run_on: resource.data.portfolio.as_of }) });
      changed(t.runSaved);
    } catch (caught) { setActionError(caught); }
    finally { setPendingPlanId(null); }
  }
  return <main className="investments-page" ref={recordRef}>
    <PageHeader title={t.title} description={t.intro} actions={activeTab === 'simulation' ? <button className="p-button" onClick={() => { setSelectedBundle(undefined); setShowOrder(true); }}>{t.simulateChange}</button> : undefined}>
      <p className="p-muted">{resource.data ? `${t.asOf} ${dateLabel(resource.data.portfolio.as_of, locale)}` : ''}</p>
    </PageHeader>
    <div className="p-tabs" role="tablist" aria-label={t.title}>
      <button role="tab" aria-selected={activeTab === 'portfolio'} onClick={() => onNavigate('investments')}>{t.portfolio}</button>
      <button role="tab" aria-selected={activeTab === 'simulation'} onClick={() => onNavigate('investments', { tab: 'simulation' })}>{t.simulation}</button>
    </div>
    <div className="investing-feedback" aria-live="polite">
      {status ? <p className="p-success">{status}</p> : null}
      {actionError && !removeHolding ? <p className="p-error" role="alert">{messageFor(actionError, locale)}</p> : null}
    </div>
    {resource.loading && !resource.data ? <Panel><p className="p-loading" role="status">{t.loading}</p></Panel> : null}
    {resource.error && !resource.data ? <Panel><EmptyState title={t.loadError} action={<button className="p-button-secondary" onClick={resource.reload}>{t.retry}</button>} /></Panel> : null}
    {resource.data ? <>
      {resource.error ? <div className="investing-stale"><span className="p-error">{t.loadError}</span><button className="p-button-ghost" onClick={resource.reload}>{t.retry}</button></div> : null}
      {activeTab === 'portfolio' ? <PortfolioView workspace={resource.data} locale={locale} focusCurrency={focusCurrency} pending={pending} onAdd={() => setHoldingDialog('new')} onEdit={setHoldingDialog} onRemove={holding => { setActionError(null); setRemoveHolding(holding); }} onImport={() => setShowImport(true)} onRefreshPrices={() => void refreshPrices()} /> : <SimulationView workspace={resource.data} locale={locale} pendingPlanId={pendingPlanId} onOrder={() => { setSelectedBundle(undefined); setShowOrder(true); }} onBundle={bundle => { setSelectedBundle(bundle.id); setShowOrder(true); }} onPlan={() => setShowPlan(true)} onTogglePlan={plan => void togglePlan(plan)} onRunPlan={plan => void runPlan(plan)} />}
      {holdingDialog ? <HoldingDialog locale={locale} defaultCurrency={currency} asOf={resource.data.portfolio.as_of} holding={holdingDialog === 'new' ? undefined : holdingDialog} onClose={() => setHoldingDialog(null)} onSaved={() => changed()} /> : null}
      {showImport ? <CsvImportDialog locale={locale} onClose={() => setShowImport(false)} onSaved={() => changed()} /> : null}
      {showOrder ? <OrderDialog locale={locale} books={resource.data.portfolio.simulation.books} bundles={resource.data.bundles} initialBundle={selectedBundle} onClose={() => setShowOrder(false)} onSaved={() => changed()} /> : null}
      {showPlan ? <PlanDialog locale={locale} books={resource.data.portfolio.simulation.books} bundles={resource.data.bundles} asOf={resource.data.portfolio.as_of} onClose={() => setShowPlan(false)} onSaved={() => changed()} /> : null}
    </> : null}
    {removeHolding ? <Modal title={t.removeTitle} onClose={() => { if (!pending) { setRemoveHolding(null); setActionError(null); } }} destructive><div className="p-stack"><p><strong>{removeHolding.name}</strong></p><p>{t.removeBody}</p>{actionError ? <p className="p-error" role="alert">{messageFor(actionError, locale)}</p> : null}<div className="p-actions"><button className="p-button-secondary" disabled={pending} onClick={() => { setRemoveHolding(null); setActionError(null); }}>{t.cancel}</button><button className="p-button-danger" disabled={pending} onClick={() => void remove()}>{pending ? t.saving : t.confirmRemove}</button></div></div></Modal> : null}
  </main>;
}
