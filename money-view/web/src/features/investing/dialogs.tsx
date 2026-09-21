import { useState, type ChangeEvent, type FormEvent } from 'react';
import { APIError, request } from '../../platform/client';
import type { Locale } from '../../platform/types';
import { EvidenceLine, Field, Modal, Money } from '../../platform/ui';
import { copy, dateTimeLabel, exactCurrencyLabel } from './copy';
import {
  holdingSchema,
  importPreviewSchema,
  importReceiptSchema,
  orderPreviewSchema,
  orderReceiptSchema,
  planSchema,
  type Book,
  type Bundle,
  type Holding,
  type ImportPreview,
  type OrderPreview,
} from './contracts';

const MAX_CSV_BYTES = 1_000_000;

export function messageFor(error: unknown, locale: Locale) {
  const t = copy(locale);
  const code = error instanceof APIError ? error.code : '';
  if (code === 'stale_quote') return t.staleQuote;
  if (code === 'insufficient_simulated_cash') return t.insufficientCash;
  if (code === 'insufficient_simulated_quantity') return t.insufficientQuantity;
  if (code === 'read_only_household' || code === 'owner_required') return t.readOnlyError;
  return t.genericError;
}

export function HoldingDialog({
  locale,
  defaultCurrency,
  asOf,
  holding,
  onClose,
  onSaved,
}: {
  locale: Locale;
  defaultCurrency: string;
  asOf: string;
  holding?: Holding;
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = copy(locale);
  const [values, setValues] = useState({
    symbol: holding?.symbol ?? '',
    name: holding?.name ?? '',
    quantity: holding?.quantity ?? '',
    total_cost: holding?.total_cost ?? '',
    currency: holding?.currency ?? defaultCurrency,
    as_of: holding?.as_of ?? asOf,
  });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const payload = holding
        ? { name: values.name, quantity: values.quantity, total_cost: values.total_cost, as_of: values.as_of }
        : { ...values, symbol: values.symbol.trim().toUpperCase(), currency: values.currency.toUpperCase() };
      await request(
        `/investing/holdings${holding ? `/${encodeURIComponent(holding.id)}` : ''}`,
        holdingSchema,
        { method: holding ? 'PATCH' : 'POST', body: JSON.stringify(payload) },
      );
      onSaved();
      onClose();
    } catch (caught) {
      setError(caught);
    } finally {
      setPending(false);
    }
  }
  function set(name: keyof typeof values, value: string) {
    setValues(current => ({ ...current, [name]: value }));
  }
  return (
    <Modal title={holding ? t.editHolding : t.addHolding} onClose={() => { if (!pending) onClose(); }}>
      <form className="p-stack" onSubmit={submit}>
        <div className="p-form-grid">
          <Field label={t.symbol}>
            <input value={values.symbol} onChange={event => set('symbol', event.target.value)} required pattern="[A-Za-z0-9.-]{1,24}" disabled={!!holding} autoCapitalize="characters" />
          </Field>
          <Field label={t.name}>
            <input value={values.name} onChange={event => set('name', event.target.value)} required maxLength={160} />
          </Field>
          <Field label={t.quantity}>
            <input value={values.quantity} onChange={event => set('quantity', event.target.value)} required inputMode="decimal" min="0.00000001" step="any" type="number" />
          </Field>
          <Field label={t.cost}>
            <input value={values.total_cost} onChange={event => set('total_cost', event.target.value)} required inputMode="decimal" min="0" step="any" type="number" />
          </Field>
          <Field label={t.currency}>
            <input value={values.currency} onChange={event => set('currency', event.target.value)} required pattern="[A-Za-z]{3}" maxLength={3} disabled={!!holding} autoCapitalize="characters" />
          </Field>
          <Field label={t.date}>
            <input value={values.as_of} onChange={event => set('as_of', event.target.value)} required type="date" />
          </Field>
        </div>
        {error ? <p className="p-error" role="alert">{messageFor(error, locale)}</p> : null}
        <div className="p-actions">
          <button type="button" className="p-button-secondary" disabled={pending} onClick={onClose}>{t.cancel}</button>
          <button className="p-button" disabled={pending}>{pending ? t.saving : t.save}</button>
        </div>
      </form>
    </Modal>
  );
}

export function CsvImportDialog({ locale, onClose, onSaved }: { locale: Locale; onClose: () => void; onSaved: () => void }) {
  const t = copy(locale);
  const [csv, setCsv] = useState('');
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<{ imported: number; duplicates: number } | null>(null);
  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > MAX_CSV_BYTES) {
      setError(t.fileTooLarge);
      return;
    }
    setCsv(await file.text());
    setPreview(null);
    setError(null);
  }
  async function validate(event: FormEvent) {
    event.preventDefault();
    if (new Blob([csv]).size > MAX_CSV_BYTES) {
      setError(t.fileTooLarge);
      return;
    }
    setPending(true);
    setError(null);
    try {
      setPreview(await request('/investing/holding-imports/preview', importPreviewSchema, { method: 'POST', body: JSON.stringify({ csv }) }));
    } catch (caught) {
      setError(messageFor(caught, locale));
    } finally {
      setPending(false);
    }
  }
  async function commit() {
    if (!preview) return;
    setPending(true);
    setError(null);
    try {
      const saved = await request(`/investing/holding-imports/${encodeURIComponent(preview.id)}/commit`, importReceiptSchema, {
        method: 'POST',
        body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
      });
      setReceipt(saved);
    } catch (caught) {
      setError(messageFor(caught, locale));
    } finally {
      setPending(false);
    }
  }
  const finishReceipt = () => { onSaved(); onClose(); };
  return (
    <Modal title={preview ? t.previewTitle : t.importCsv} onClose={() => { if (!pending) { if (receipt) finishReceipt(); else onClose(); } }}>
      {receipt ? (
        <div className="p-stack">
          <p className="p-success" role="status">{t.imported}: {receipt.imported}. {t.duplicates}: {receipt.duplicates}.</p>
          <button className="p-button" onClick={finishReceipt}>{t.close}</button>
        </div>
      ) : preview ? (
        <div className="p-stack">
          <p><strong>{preview.valid_count}</strong> {t.validRows} · <strong>{preview.duplicate_count}</strong> {t.duplicates}</p>
          {preview.errors.length > 0 ? (
            <div className="p-error" role="alert">
              <p>{t.importErrors}</p>
              <ul>{preview.errors.map(item => <li key={`${item.line}-${item.code}`}>{t.date} {item.line}: {item.code}</li>)}</ul>
            </div>
          ) : null}
          <div className="p-table-wrap">
            <table className="p-table">
              <thead><tr><th>{t.symbol}</th><th>{t.name}</th><th>{t.quantity}</th><th>{t.cost}</th><th>{t.currency}</th><th>{t.rowStatus}</th></tr></thead>
              <tbody>{preview.rows.slice(0, 25).map(row => <tr key={row.line}><td>{row.symbol}</td><td>{row.name}</td><td>{row.quantity}</td><td><Money amount={row.total_cost} currency={row.currency} locale={locale} /></td><td>{row.currency}</td><td>{row.duplicate ? t.duplicates : t.ready}</td></tr>)}</tbody>
            </table>
          </div>
          <EvidenceLine evidence={preview.source} locale={locale} />
          {error ? <p className="p-error" role="alert">{error}</p> : null}
          <div className="p-actions">
            <button className="p-button-secondary" disabled={pending} onClick={() => setPreview(null)}>{t.cancel}</button>
            <button className="p-button" disabled={pending || !preview.can_commit} onClick={() => void commit()}>{pending ? t.saving : t.commitImport}</button>
          </div>
        </div>
      ) : (
        <form className="p-stack" onSubmit={validate}>
          <Field label={t.csvFile} help={t.csvHint}>
            <input type="file" accept=".csv,text/csv" onChange={event => void readFile(event)} />
          </Field>
          <Field label={t.csvContent}>
            <textarea rows={9} required value={csv} onChange={event => { setCsv(event.target.value); setError(null); }} />
          </Field>
          {error ? <p className="p-error" role="alert">{error}</p> : null}
          <div className="p-actions">
            <button type="button" className="p-button-secondary" disabled={pending} onClick={onClose}>{t.cancel}</button>
            <button className="p-button" disabled={pending || !csv.trim()}>{pending ? t.previewing : t.previewImport}</button>
          </div>
        </form>
      )}
    </Modal>
  );
}

export function OrderDialog({
  locale,
  books,
  bundles,
  initialBundle,
  onClose,
  onSaved,
}: {
  locale: Locale;
  books: Book[];
  bundles: Bundle[];
  initialBundle?: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = copy(locale);
  const [values, setValues] = useState({
    book_id: books[0]?.id ?? '',
    side: 'buy',
    kind: initialBundle ? 'bundle' : 'symbol',
    symbol: '',
    quantity: '',
    bundle_id: initialBundle ?? bundles[0]?.id ?? '',
    amount: '',
  });
  const [preview, setPreview] = useState<OrderPreview | null>(null);
  const [receipt, setReceipt] = useState<Awaited<ReturnType<typeof confirmOrder>> | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function createPreview(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const payload = values.kind === 'bundle'
        ? { book_id: values.book_id, side: 'buy', bundle_id: values.bundle_id, amount: values.amount }
        : { book_id: values.book_id, side: values.side, symbol: values.symbol.trim().toUpperCase(), quantity: values.quantity };
      setPreview(await request('/investing/orders/preview', orderPreviewSchema, { method: 'POST', body: JSON.stringify(payload) }));
    } catch (caught) {
      setError(caught);
    } finally {
      setPending(false);
    }
  }
  async function confirmOrder(previewId: string) {
    return request(`/investing/orders/${encodeURIComponent(previewId)}/confirm`, orderReceiptSchema, {
      method: 'POST', body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
    });
  }
  async function confirm() {
    if (!preview) return;
    setPending(true);
    setError(null);
    try {
      const saved = await confirmOrder(preview.id);
      setReceipt(saved);
    } catch (caught) {
      setError(caught);
    } finally {
      setPending(false);
    }
  }
  if (receipt) {
    const finishReceipt = () => { onSaved(); onClose(); };
    return (
      <Modal title={t.confirmedReceipt} onClose={finishReceipt}>
        <div className="p-stack investing-receipt">
          <p className="p-success" role="status">{t.saved}</p>
          <div className="p-metrics">
            <div className="p-metric"><span>{t.gross}</span><strong><Money amount={receipt.gross} currency={receipt.currency} locale={locale} /></strong></div>
            <div className="p-metric"><span>{t.roundingCost}</span><strong><data value={receipt.rounding_cost}>{exactCurrencyLabel(receipt.rounding_cost, receipt.currency)}</data></strong></div>
            <div className="p-metric"><span>{t.cashBefore}</span><strong><Money amount={receipt.cash_before} currency={receipt.currency} locale={locale} /></strong></div>
            <div className="p-metric"><span>{t.cashAfter}</span><strong><Money amount={receipt.cash_after} currency={receipt.currency} locale={locale} /></strong></div>
          </div>
          <p className="p-muted"><strong>{t.roundingRule}:</strong> {t.roundingRuleDetail}</p>
          <p className="p-muted">{t.confirmedAt}: {dateTimeLabel(receipt.confirmed_at, locale)}</p>
          <EvidenceLine evidence={receipt.source} locale={locale} />
          <button className="p-button" onClick={finishReceipt}>{t.close}</button>
        </div>
      </Modal>
    );
  }
  if (preview) {
    return (
      <Modal title={t.previewReady} onClose={() => { if (!pending) onClose(); }}>
        <div className="p-stack investing-receipt">
          <p className="p-muted">{t.simulatedBoundary}</p>
          <div className="p-metrics">
            <div className="p-metric"><span>{t.gross}</span><strong><Money amount={preview.gross} currency={preview.currency} locale={locale} /></strong></div>
            <div className="p-metric"><span>{t.roundingCost}</span><strong><data value={preview.rounding_cost}>{exactCurrencyLabel(preview.rounding_cost, preview.currency)}</data></strong></div>
            <div className="p-metric"><span>{t.fee}</span><strong><Money amount={preview.fee} currency={preview.currency} locale={locale} /></strong></div>
            <div className="p-metric"><span>{t.cashEffect}</span><strong><Money amount={preview.cash_effect} currency={preview.currency} locale={locale} /></strong></div>
          </div>
          <p className="p-muted"><strong>{t.roundingRule}:</strong> {t.roundingRuleDetail}</p>
          <div className="investing-legs">{preview.legs.map(leg => <div className="investing-leg" key={leg.symbol}><strong>{leg.symbol}</strong><span>{leg.quantity} × <Money amount={leg.price} currency={preview.currency} locale={locale} /></span><EvidenceLine evidence={leg.price_source} locale={locale} /></div>)}</div>
          <p className="p-muted">{t.expires}: {dateTimeLabel(preview.expires_at, locale)}</p>
          <EvidenceLine evidence={preview.source} locale={locale} />
          {error ? <p className="p-error" role="alert">{messageFor(error, locale)}</p> : null}
          <div className="p-actions">
            <button className="p-button-secondary" disabled={pending} onClick={() => { setPreview(null); setError(null); }}>{t.cancel}</button>
            <button className="p-button" disabled={pending} onClick={() => void confirm()}>{pending ? t.confirming : t.confirmSimulation}</button>
          </div>
        </div>
      </Modal>
    );
  }
  return (
    <Modal title={t.newSimulation} onClose={() => { if (!pending) onClose(); }}>
      <form className="p-stack" onSubmit={createPreview}>
        <p className="p-muted">{t.simulatedBoundary}</p>
        <div className="p-form-grid">
          <Field label={t.book}><select required value={values.book_id} onChange={event => setValues(current => ({ ...current, book_id: event.target.value }))}>{books.map(book => <option key={book.id} value={book.id}>{book.name} · {book.currency}</option>)}</select></Field>
          <Field label={t.target}><select value={values.kind} onChange={event => setValues(current => ({ ...current, kind: event.target.value }))}><option value="symbol">{t.singleAsset}</option>{bundles.length > 0 ? <option value="bundle">{t.curatedBundle}</option> : null}</select></Field>
          {values.kind === 'symbol' ? <>
            <Field label={t.side}><select value={values.side} onChange={event => setValues(current => ({ ...current, side: event.target.value }))}><option value="buy">{t.buy}</option><option value="sell">{t.sell}</option></select></Field>
            <Field label={t.symbol}><input required pattern="[A-Za-z0-9.-]{1,24}" value={values.symbol} onChange={event => setValues(current => ({ ...current, symbol: event.target.value }))} autoCapitalize="characters" /></Field>
            <Field label={t.quantity}><input required type="number" inputMode="decimal" min="0.00000001" step="any" value={values.quantity} onChange={event => setValues(current => ({ ...current, quantity: event.target.value }))} /></Field>
          </> : <>
            <Field label={t.curatedBundle}><select required value={values.bundle_id} onChange={event => setValues(current => ({ ...current, bundle_id: event.target.value }))}>{bundles.map(bundle => <option key={bundle.id} value={bundle.id}>{bundle.name}</option>)}</select></Field>
            <Field label={t.amount}><input required type="number" inputMode="decimal" min="0.01" step="any" value={values.amount} onChange={event => setValues(current => ({ ...current, amount: event.target.value }))} /></Field>
          </>}
        </div>
        {error ? <p className="p-error" role="alert">{messageFor(error, locale)}</p> : null}
        <div className="p-actions"><button type="button" className="p-button-secondary" disabled={pending} onClick={onClose}>{t.cancel}</button><button className="p-button" disabled={pending || books.length === 0}>{pending ? t.previewing : t.preview}</button></div>
      </form>
    </Modal>
  );
}

export function PlanDialog({ locale, books, bundles, asOf, onClose, onSaved }: { locale: Locale; books: Book[]; bundles: Bundle[]; asOf: string; onClose: () => void; onSaved: () => void }) {
  const t = copy(locale);
  const [values, setValues] = useState({ book_id: books[0]?.id ?? '', cadence: 'monthly', next_run_on: asOf, kind: 'symbol', symbol: '', bundle_id: bundles[0]?.id ?? '', amount: '' });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const target = values.kind === 'bundle' ? { bundle_id: values.bundle_id } : { symbol: values.symbol.trim().toUpperCase() };
      await request('/investing/recurring-plans', planSchema, { method: 'POST', body: JSON.stringify({ book_id: values.book_id, cadence: values.cadence, next_run_on: values.next_run_on, amount: values.amount, ...target }) });
      onSaved();
      onClose();
    } catch (caught) {
      setError(caught);
    } finally {
      setPending(false);
    }
  }
  return (
    <Modal title={t.createPlan} onClose={() => { if (!pending) onClose(); }}>
      <form className="p-stack" onSubmit={submit}>
        <p className="p-muted">{t.recurringIntro}</p>
        <div className="p-form-grid">
          <Field label={t.book}><select required value={values.book_id} onChange={event => setValues(current => ({ ...current, book_id: event.target.value }))}>{books.map(book => <option value={book.id} key={book.id}>{book.name} · {book.currency}</option>)}</select></Field>
          <Field label={t.cadence}><select value={values.cadence} onChange={event => setValues(current => ({ ...current, cadence: event.target.value }))}><option value="weekly">{t.weekly}</option><option value="monthly">{t.monthly}</option></select></Field>
          <Field label={t.nextRun}><input required type="date" value={values.next_run_on} onChange={event => setValues(current => ({ ...current, next_run_on: event.target.value }))} /></Field>
          <Field label={t.target}><select value={values.kind} onChange={event => setValues(current => ({ ...current, kind: event.target.value }))}><option value="symbol">{t.singleAsset}</option>{bundles.length > 0 ? <option value="bundle">{t.curatedBundle}</option> : null}</select></Field>
          {values.kind === 'bundle' ? <Field label={t.curatedBundle}><select required value={values.bundle_id} onChange={event => setValues(current => ({ ...current, bundle_id: event.target.value }))}>{bundles.map(bundle => <option value={bundle.id} key={bundle.id}>{bundle.name}</option>)}</select></Field> : <Field label={t.symbol}><input required pattern="[A-Za-z0-9.-]{1,24}" value={values.symbol} onChange={event => setValues(current => ({ ...current, symbol: event.target.value }))} /></Field>}
          <Field label={t.amount}><input required type="number" inputMode="decimal" min="0.01" step="any" value={values.amount} onChange={event => setValues(current => ({ ...current, amount: event.target.value }))} /></Field>
        </div>
        {error ? <p className="p-error" role="alert">{messageFor(error, locale)}</p> : null}
        <div className="p-actions"><button type="button" className="p-button-secondary" disabled={pending} onClick={onClose}>{t.cancel}</button><button className="p-button" disabled={pending || books.length === 0}>{pending ? t.saving : t.createPlan}</button></div>
      </form>
    </Modal>
  );
}
