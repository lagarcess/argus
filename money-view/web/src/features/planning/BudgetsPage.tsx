import { useState, type FormEvent, type ReactNode } from 'react';
import { Check, Pause, Pencil, Play, Plus, SkipForward } from 'lucide-react';
import { z } from 'zod';
import { APIError, request } from '../../platform/client';
import { useRecordFocus } from '../../argus/useRecordFocus';
import { useResource } from '../../platform/hooks';
import type { PlatformPageProps } from '../../platform/types';
import {
  EmptyState,
  EvidenceLine,
  Field,
  Modal,
  Money,
  PageHeader,
  Panel,
} from '../../platform/ui';
import { cadenceLabel, categoryLabel, planningCopy, statusLabel } from './copy';
import {
  accountsResponseSchema,
  billSchema,
  billsResponseSchema,
  budgetSchema,
  budgetsResponseSchema,
  categoriesResponseSchema,
  decimalSchema,
  planningPaths,
  type Account,
  type Bill,
  type Budget,
} from './contracts';
import {
  currentMonth,
  errorMessage,
  ErrorState,
  formatDate,
  formatMonth,
  InlineError,
  LoadingState,
  signedAmountClass,
} from './shared';

const budgetDraftSchema = z.object({
  category: z.string().min(1),
  currency: z.string().trim().length(3),
  month: z.string().regex(/^\d{4}-\d{2}$/),
  limit: decimalSchema.refine((value) => Number(value) > 0),
});

const billDraftSchema = z.object({
  name: z.string().trim().min(1),
  account_id: z.string().min(1),
  category: z.string().min(1),
  currency: z.string().trim().length(3),
  amount: decimalSchema.refine((value) => Number(value) > 0),
  cadence: z.enum(['weekly', 'monthly', 'quarterly', 'yearly']),
  anchor_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
});

type PlanningData = {
  month: string;
  budgets: Budget[];
  bills: Bill[];
  accounts: Account[];
  categories: string[];
};

type DraftErrors = Record<string, string>;

function fieldErrors(result: z.ZodSafeParseError<unknown>, message: string): DraftErrors {
  return Object.fromEntries(result.error.issues.map((issue) => [String(issue.path[0]), message]));
}

function BudgetModal({
  locale,
  currency,
  month,
  categories,
  budget,
  onClose,
  onSaved,
}: {
  locale: PlatformPageProps['locale'];
  currency: string;
  month: string;
  categories: string[];
  budget: Budget | null;
  onClose: () => void;
  onSaved: () => void;
}): ReactNode {
  const copy = planningCopy(locale);
  const [category, setCategory] = useState(budget?.category ?? categories[0] ?? '');
  const [selectedCurrency, setSelectedCurrency] = useState(budget?.currency ?? currency);
  const [selectedMonth, setSelectedMonth] = useState(budget?.month ?? month);
  const [limit, setLimit] = useState(budget?.limit ?? '');
  const [errors, setErrors] = useState<DraftErrors>({});
  const [requestError, setRequestError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const result = budgetDraftSchema.safeParse({
      category,
      currency: selectedCurrency.toUpperCase(),
      month: selectedMonth,
      limit,
    });
    if (!result.success) {
      setErrors(fieldErrors(result, copy.errors.required));
      return;
    }
    setErrors({});
    setRequestError(null);
    setPending(true);
    try {
      const path = budget
        ? `${planningPaths.budgets}/${encodeURIComponent(budget.id)}`
        : planningPaths.budgets;
      await request(path, z.unknown(), {
        method: budget ? 'PUT' : 'POST',
        body: JSON.stringify(result.data),
      });
      onSaved();
    } catch (error) {
      setRequestError(errorMessage(error, locale));
    } finally {
      setPending(false);
    }
  }

  return (
    <Modal
      title={budget ? copy.budgets.editTitle : copy.budgets.createTitle}
      onClose={onClose}
      footer={
        <>
          <button className="p-button-secondary" type="button" onClick={onClose} disabled={pending}>
            {copy.common.cancel}
          </button>
          <button className="p-button" type="submit" form="planning-budget-form" disabled={pending}>
            {pending ? copy.common.saving : copy.common.save}
          </button>
        </>
      }
    >
      <form id="planning-budget-form" className="p-stack" onSubmit={(event) => void submit(event)}>
        <Field label={copy.budgets.category} error={errors.category}>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">{copy.budgets.category}</option>
            {categories.map((item) => (
              <option key={item} value={item}>
                {categoryLabel(item, locale)}
              </option>
            ))}
          </select>
        </Field>
        <div className="p-form-grid">
          <Field label={copy.budgets.currency} error={errors.currency}>
            <input
              inputMode="text"
              maxLength={3}
              value={selectedCurrency}
              onChange={(event) => setSelectedCurrency(event.target.value.toUpperCase())}
            />
          </Field>
          <Field label={copy.budgets.month} error={errors.month}>
            <input type="month" value={selectedMonth} onChange={(event) => setSelectedMonth(event.target.value)} />
          </Field>
        </div>
        <Field label={copy.budgets.limit} help={copy.budgets.limitHelp} error={errors.limit}>
          <input
            inputMode="decimal"
            type="number"
            min="0.01"
            step="0.01"
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
          />
        </Field>
        {requestError && <InlineError>{requestError}</InlineError>}
      </form>
    </Modal>
  );
}

function BillModal({
  locale,
  accounts,
  categories,
  bill,
  onClose,
  onSaved,
}: {
  locale: PlatformPageProps['locale'];
  accounts: Account[];
  categories: string[];
  bill: Bill | null;
  onClose: () => void;
  onSaved: () => void;
}): ReactNode {
  const copy = planningCopy(locale);
  const initialAccount = accounts.find((account) => account.id === bill?.account_id) ?? accounts[0];
  const [name, setName] = useState(bill?.name ?? '');
  const [accountId, setAccountId] = useState(bill?.account_id ?? initialAccount?.id ?? '');
  const [category, setCategory] = useState(bill?.category ?? categories[0] ?? '');
  const [currency, setCurrency] = useState(bill?.currency ?? initialAccount?.currency ?? '');
  const [amount, setAmount] = useState(bill?.amount ?? '');
  const [cadence, setCadence] = useState<'weekly' | 'monthly' | 'quarterly' | 'yearly'>(
    bill?.cadence ?? 'monthly',
  );
  const [anchorDate, setAnchorDate] = useState(bill?.anchor_date ?? new Date().toISOString().slice(0, 10));
  const [errors, setErrors] = useState<DraftErrors>({});
  const [requestError, setRequestError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function chooseAccount(nextId: string): void {
    setAccountId(nextId);
    const account = accounts.find((item) => item.id === nextId);
    if (account) setCurrency(account.currency);
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const result = billDraftSchema.safeParse({
      name,
      account_id: accountId,
      category,
      currency,
      amount,
      cadence,
      anchor_date: anchorDate,
    });
    if (!result.success) {
      setErrors(fieldErrors(result, copy.errors.required));
      return;
    }
    setErrors({});
    setRequestError(null);
    setPending(true);
    try {
      const path = bill
        ? `${planningPaths.bills}/${encodeURIComponent(bill.id)}`
        : planningPaths.bills;
      await request(path, z.unknown(), {
        method: bill ? 'PUT' : 'POST',
        body: JSON.stringify(result.data),
      });
      onSaved();
    } catch (error) {
      setRequestError(errorMessage(error, locale));
    } finally {
      setPending(false);
    }
  }

  return (
    <Modal
      title={bill ? copy.bills.editTitle : copy.bills.createTitle}
      onClose={onClose}
      footer={
        <>
          <button className="p-button-secondary" type="button" onClick={onClose} disabled={pending}>
            {copy.common.cancel}
          </button>
          <button className="p-button" type="submit" form="planning-bill-form" disabled={pending}>
            {pending ? copy.common.saving : copy.common.save}
          </button>
        </>
      }
    >
      <form id="planning-bill-form" className="p-stack" onSubmit={(event) => void submit(event)}>
        <Field label={copy.bills.name} error={errors.name}>
          <input value={name} maxLength={120} onChange={(event) => setName(event.target.value)} />
        </Field>
        <Field label={copy.bills.account} error={errors.account_id}>
          <select value={accountId} onChange={(event) => chooseAccount(event.target.value)}>
            <option value="">{copy.bills.account}</option>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name} · {account.currency}
              </option>
            ))}
          </select>
        </Field>
        <div className="p-form-grid">
          <Field label={copy.budgets.category} error={errors.category}>
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">{copy.budgets.category}</option>
              {categories.map((item) => (
                <option key={item} value={item}>
                  {categoryLabel(item, locale)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={copy.budgets.currency} error={errors.currency}>
            <input value={currency} readOnly />
          </Field>
        </div>
        <Field label={copy.bills.amount} error={errors.amount}>
          <input
            inputMode="decimal"
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </Field>
        <div className="p-form-grid">
          <Field label={copy.bills.cadence} error={errors.cadence}>
            <select value={cadence} onChange={(event) => setCadence(event.target.value as typeof cadence)}>
              {(['weekly', 'monthly', 'quarterly', 'yearly'] as const).map((value) => (
                <option key={value} value={value}>
                  {cadenceLabel(value, locale)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={copy.bills.anchorDate} error={errors.anchor_date}>
            <input type="date" value={anchorDate} onChange={(event) => setAnchorDate(event.target.value)} />
          </Field>
        </div>
        <p className="p-muted">{copy.bills.localOnly}</p>
        {requestError && <InlineError>{requestError}</InlineError>}
      </form>
    </Modal>
  );
}

export function BudgetsPage({
  locale,
  currency,
  query,
  revision,
  onNavigate,
  onChanged,
}: PlatformPageProps): ReactNode {
  const copy = planningCopy(locale);
  const [budgetModal, setBudgetModal] = useState<Budget | 'new' | null>(null);
  const [billModal, setBillModal] = useState<Bill | 'new' | null>(null);
  const [mutation, setMutation] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const selectedRecord = query.get('record_id');
  const requestedMonth = query.get('month');
  const monthFilter = requestedMonth && /^\d{4}-\d{2}$/.test(requestedMonth) ? requestedMonth : currentMonth();
  const resource = useResource<PlanningData>(async () => {
    const [bills, accounts, categories] = await Promise.all([
      request(planningPaths.bills, billsResponseSchema),
      request(`${planningPaths.accounts}?limit=100&offset=0`, accountsResponseSchema),
      request(planningPaths.categories, categoriesResponseSchema),
    ]);
    const selectedBudget = selectedRecord && !bills.items.some((bill) => bill.id === selectedRecord)
      ? await request(`${planningPaths.budgets}/${encodeURIComponent(selectedRecord)}`, budgetSchema)
      : null;
    const month = selectedBudget?.month ?? monthFilter;
    const budgets = await request(`${planningPaths.budgets}?month=${encodeURIComponent(month)}`, budgetsResponseSchema);
    return {
      month,
      budgets: selectedBudget
        ? [selectedBudget, ...budgets.items.filter((budget) => budget.id !== selectedBudget.id)]
        : budgets.items,
      bills: bills.items,
      accounts: accounts.items,
      categories: categories.items
        .filter((item) => item.kind === 'expense')
        .map((item) => item.id),
    };
  }, [monthFilter, selectedRecord, revision]);
  const recordRef = useRecordFocus(selectedRecord, [resource.data]);

  function changeMonth(nextMonth: string): void {
    onNavigate('budgets', { month: nextMonth });
  }

  function saved(): void {
    setBudgetModal(null);
    setBillModal(null);
    resource.reload();
    onChanged();
  }

  async function billAction(bill: Bill, action: 'pause' | 'skip' | 'pay'): Promise<void> {
    const key = `${bill.id}:${action}`;
    setMutation(key);
    setMutationError(null);
    try {
      const path = `${planningPaths.bills}/${encodeURIComponent(bill.id)}/${action}`;
      const body =
        action === 'pause'
          ? { paused: bill.status !== 'paused' }
          : action === 'pay'
            ? { due_date: bill.next_due }
            : undefined;
      await request(path, z.unknown(), {
        method: 'POST',
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      resource.reload();
      onChanged();
    } catch (error) {
      setMutationError(errorMessage(error, locale));
    } finally {
      setMutation(null);
    }
  }

  if (!resource.data && resource.loading) return <LoadingState label={copy.common.loading} />;
  if (!resource.data && resource.error) {
    const missingRecord = selectedRecord && resource.error instanceof APIError && resource.error.status === 404;
    return (
      <div className="p-stack">
        <ErrorState
          message={missingRecord
            ? locale === 'en' ? 'This record is no longer available in this household.' : 'Este registro ya no está disponible en este hogar.'
            : errorMessage(resource.error, locale)}
          retryLabel={copy.common.retry}
          onRetry={resource.reload}
        />
        {selectedRecord && <button className="p-button-secondary" type="button" onClick={() => onNavigate('budgets')}>
          {locale === 'en' ? 'View current budgets' : 'Ver presupuestos actuales'}
        </button>}
      </div>
    );
  }
  if (!resource.data) return null;

  const data = resource.data;
  const month = data.month;
  return (
    <div className="planning-page planning-budgets-page" ref={recordRef}>
      <PageHeader
        title={copy.budgets.title}
        description={copy.budgets.description}
        actions={
          <button className="p-button" type="button" onClick={() => setBudgetModal('new')}>
            <Plus size={17} aria-hidden="true" />
            {copy.budgets.add}
          </button>
        }
      />
      <div className="p-toolbar planning-period-toolbar">
        <Field label={copy.budgets.month}>
          <input type="month" value={month} onChange={(event) => changeMonth(event.target.value)} />
        </Field>
        <span className="p-muted">{formatMonth(month, locale)}</span>
        {resource.loading && <span className="p-muted" role="status">{copy.common.loading}</span>}
      </div>

      <Panel aria-labelledby="budget-list-title">
        <div className="planning-section-heading">
          <div>
            <h2 id="budget-list-title">{copy.budgets.title}</h2>
            <p className="p-muted">{formatMonth(month, locale)}</p>
          </div>
        </div>
        {data.budgets.length === 0 ? (
          <EmptyState
            title={copy.budgets.empty}
            description={copy.budgets.emptyDescription}
            action={
              <button className="p-button" type="button" onClick={() => setBudgetModal('new')}>
                {copy.budgets.add}
              </button>
            }
          />
        ) : (
          <div className="p-table-wrap planning-table-wrap">
            <table className="p-table planning-table">
              <thead>
                <tr>
                  <th scope="col">{copy.budgets.category}</th>
                  <th scope="col">{copy.budgets.actual}</th>
                  <th scope="col">{copy.budgets.limit}</th>
                  <th scope="col">{copy.budgets.remaining}</th>
                  <th scope="col" className="planning-action-column">{copy.budgets.actions}</th>
                </tr>
              </thead>
              <tbody>
                {data.budgets.map((budget) => (
                  <tr
                    key={budget.id}
                    data-record-id={budget.id}
                    tabIndex={selectedRecord === budget.id ? -1 : undefined}
                    className={selectedRecord === budget.id ? 'planning-highlight' : undefined}
                  >
                    <td data-label={copy.budgets.category}>
                      <strong>{categoryLabel(budget.category, locale)}</strong>
                      <EvidenceLine evidence={budget.evidence} locale={locale} />
                    </td>
                    <td data-label={copy.budgets.actual}>
                      <Money amount={budget.actual} currency={budget.currency} locale={locale} />
                    </td>
                    <td data-label={copy.budgets.limit}>
                      <Money amount={budget.limit} currency={budget.currency} locale={locale} />
                    </td>
                    <td data-label={copy.budgets.remaining}>
                      <span className={signedAmountClass(budget.remaining)}>
                        <Money amount={budget.remaining} currency={budget.currency} locale={locale} />
                      </span>
                      {Number(budget.remaining) < 0 && (
                        <small className="planning-status-text">{copy.budgets.exceeded}</small>
                      )}
                    </td>
                    <td data-label={copy.budgets.actions}>
                      <button className="p-button-ghost" type="button" onClick={() => setBudgetModal(budget)}>
                        <Pencil size={15} aria-hidden="true" />
                        {copy.common.edit}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel aria-labelledby="bill-list-title">
        <div className="planning-section-heading">
          <div>
            <h2 id="bill-list-title">{copy.bills.title}</h2>
            <p className="p-muted">{copy.bills.description}</p>
          </div>
          <button
            className="p-button-secondary"
            type="button"
            disabled={data.accounts.length === 0}
            onClick={() => setBillModal('new')}
          >
            <Plus size={17} aria-hidden="true" />
            {copy.bills.add}
          </button>
        </div>
        {data.accounts.length === 0 && <p className="p-muted">{copy.bills.missingAccounts}</p>}
        {mutationError && <InlineError>{mutationError}</InlineError>}
        {data.bills.length === 0 ? (
          <EmptyState
            title={copy.bills.empty}
            description={copy.bills.emptyDescription}
            action={
              data.accounts.length > 0 ? (
                <button className="p-button" type="button" onClick={() => setBillModal('new')}>
                  {copy.bills.add}
                </button>
              ) : undefined
            }
          />
        ) : (
          <div className="p-table-wrap planning-table-wrap">
            <table className="p-table planning-table planning-bills-table">
              <thead>
                <tr>
                  <th scope="col">{copy.bills.name}</th>
                  <th scope="col">{copy.bills.amount}</th>
                  <th scope="col">{copy.bills.cadence}</th>
                  <th scope="col">{copy.bills.nextDue}</th>
                  <th scope="col">{copy.bills.status}</th>
                  <th scope="col" className="planning-action-column">{copy.bills.actions}</th>
                </tr>
              </thead>
              <tbody>
                {data.bills.map((bill) => {
                  const paused = bill.status === 'paused';
                  return (
                    <tr key={bill.id} data-record-id={bill.id}>
                      <td data-label={copy.bills.name}>
                        <strong>{bill.name}</strong>
                        <span className="p-muted">{categoryLabel(bill.category, locale)}</span>
                        <EvidenceLine evidence={bill.evidence} locale={locale} />
                      </td>
                      <td data-label={copy.bills.amount}>
                        <Money amount={bill.amount} currency={bill.currency} locale={locale} />
                      </td>
                      <td data-label={copy.bills.cadence}>{cadenceLabel(bill.cadence, locale)}</td>
                      <td data-label={copy.bills.nextDue}>{formatDate(bill.next_due, locale)}</td>
                      <td data-label={copy.bills.status}>
                        <span className="p-badge">{statusLabel(bill.status, locale)}</span>
                      </td>
                      <td data-label={copy.bills.actions}>
                        <div className="planning-row-actions">
                          <button className="p-button-ghost" type="button" onClick={() => setBillModal(bill)}>
                            <Pencil size={15} aria-hidden="true" />
                            {copy.common.edit}
                          </button>
                          <button
                            className="p-button-ghost"
                            type="button"
                            disabled={mutation !== null}
                            onClick={() => void billAction(bill, 'pause')}
                          >
                            {paused ? <Play size={15} aria-hidden="true" /> : <Pause size={15} aria-hidden="true" />}
                            {paused ? copy.bills.resume : copy.bills.pause}
                          </button>
                          <button
                            className="p-button-ghost"
                            type="button"
                            disabled={mutation !== null || paused}
                            onClick={() => void billAction(bill, 'skip')}
                          >
                            <SkipForward size={15} aria-hidden="true" />
                            {copy.bills.skip}
                          </button>
                          <button
                            className="p-button-secondary"
                            type="button"
                            disabled={mutation !== null || paused}
                            onClick={() => void billAction(bill, 'pay')}
                          >
                            <Check size={15} aria-hidden="true" />
                            {copy.bills.pay}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {budgetModal && (
        <BudgetModal
          locale={locale}
          currency={currency}
          month={month}
          categories={data.categories}
          budget={budgetModal === 'new' ? null : budgetModal}
          onClose={() => setBudgetModal(null)}
          onSaved={saved}
        />
      )}
      {billModal && (
        <BillModal
          locale={locale}
          accounts={data.accounts}
          categories={data.categories}
          bill={billModal === 'new' ? null : billModal}
          onClose={() => setBillModal(null)}
          onSaved={saved}
        />
      )}
    </div>
  );
}
