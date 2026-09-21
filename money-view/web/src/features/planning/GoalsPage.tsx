import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { Archive, Pencil, Plus, WalletCards } from 'lucide-react';
import { z } from 'zod';
import { request } from '../../platform/client';
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
import { planningCopy, statusLabel } from './copy';
import {
  accountsResponseSchema,
  decimalSchema,
  goalSchema,
  goalsResponseSchema,
  planningPaths,
  type Account,
  type Goal,
} from './contracts';
import { errorMessage, ErrorState, formatDate, InlineError, LoadingState } from './shared';

const goalDraftSchema = z.object({
  name: z.string().trim().min(1),
  target_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  target_amount: decimalSchema.refine((value) => Number(value) > 0),
  monthly_contribution: decimalSchema.refine((value) => Number(value) >= 0),
  currency: z.string().trim().length(3),
});

type GoalData = {
  goals: Goal[];
  accounts: Account[];
};

type GoalErrors = Record<string, string>;

function GoalModal({
  locale,
  defaultCurrency,
  goal,
  onClose,
  onSaved,
}: {
  locale: PlatformPageProps['locale'];
  defaultCurrency: string;
  goal: Goal | null;
  onClose: () => void;
  onSaved: () => void;
}): ReactNode {
  const copy = planningCopy(locale);
  const [name, setName] = useState(goal?.name ?? '');
  const [targetDate, setTargetDate] = useState(goal?.target_date ?? '');
  const [targetAmount, setTargetAmount] = useState(goal?.target_amount ?? '');
  const [monthlyContribution, setMonthlyContribution] = useState(goal?.monthly_contribution ?? '0');
  const [currency, setCurrency] = useState(goal?.currency ?? defaultCurrency);
  const [errors, setErrors] = useState<GoalErrors>({});
  const [requestError, setRequestError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const result = goalDraftSchema.safeParse({
      name,
      target_date: targetDate,
      target_amount: targetAmount,
      monthly_contribution: monthlyContribution,
      currency: currency.toUpperCase(),
    });
    if (!result.success) {
      setErrors(
        Object.fromEntries(
          result.error.issues.map((issue) => [String(issue.path[0]), copy.errors.required]),
        ),
      );
      return;
    }
    setErrors({});
    setRequestError(null);
    setPending(true);
    try {
      const path = goal
        ? `${planningPaths.goals}/${encodeURIComponent(goal.id)}`
        : planningPaths.goals;
      await request(path, z.unknown(), {
        method: goal ? 'PUT' : 'POST',
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
      title={goal ? copy.goals.editTitle : copy.goals.createTitle}
      onClose={onClose}
      footer={
        <>
          <button className="p-button-secondary" type="button" onClick={onClose} disabled={pending}>
            {copy.common.cancel}
          </button>
          <button className="p-button" type="submit" form="planning-goal-form" disabled={pending}>
            {pending ? copy.common.saving : copy.common.save}
          </button>
        </>
      }
    >
      <form id="planning-goal-form" className="p-stack" onSubmit={(event) => void submit(event)}>
        <Field label={copy.goals.name} error={errors.name}>
          <input value={name} maxLength={120} onChange={(event) => setName(event.target.value)} />
        </Field>
        <div className="p-form-grid">
          <Field label={copy.goals.target} error={errors.target_amount}>
            <input
              inputMode="decimal"
              type="number"
              min="0.01"
              step="0.01"
              value={targetAmount}
              onChange={(event) => setTargetAmount(event.target.value)}
            />
          </Field>
          <Field label={copy.goals.currency} error={errors.currency}>
            <input
              maxLength={3}
              value={currency}
              onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            />
          </Field>
        </div>
        <div className="p-form-grid">
          <Field label={copy.goals.date} error={errors.target_date}>
            <input type="date" value={targetDate} onChange={(event) => setTargetDate(event.target.value)} />
          </Field>
          <Field label={copy.goals.monthly} error={errors.monthly_contribution}>
            <input
              inputMode="decimal"
              type="number"
              min="0"
              step="0.01"
              value={monthlyContribution}
              onChange={(event) => setMonthlyContribution(event.target.value)}
            />
          </Field>
        </div>
        {requestError && <InlineError>{requestError}</InlineError>}
      </form>
    </Modal>
  );
}

function AllocationModal({
  locale,
  goal,
  accounts,
  onClose,
  onSaved,
}: {
  locale: PlatformPageProps['locale'];
  goal: Goal;
  accounts: Account[];
  onClose: () => void;
  onSaved: () => void;
}): ReactNode {
  const copy = planningCopy(locale);
  const eligible = accounts.filter((account) => account.currency === goal.currency);
  const existing = new Map(goal.allocations.map((allocation) => [allocation.account_id, allocation.amount]));
  const [amounts, setAmounts] = useState<Record<string, string>>(
    Object.fromEntries(eligible.map((account) => [account.id, existing.get(account.id) ?? ''])),
  );
  const [requestError, setRequestError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const allocations = eligible
      .map((account) => ({ account_id: account.id, amount: amounts[account.id]?.trim() ?? '' }))
      .filter((allocation) => allocation.amount !== '' && Number(allocation.amount) !== 0);
    const invalid = allocations.some(
      (allocation) => !decimalSchema.safeParse(allocation.amount).success || Number(allocation.amount) < 0,
    );
    if (invalid) {
      setRequestError(copy.errors.invalidNumber);
      return;
    }
    setRequestError(null);
    setPending(true);
    try {
      await request(`${planningPaths.goals}/${encodeURIComponent(goal.id)}/allocations`, goalSchema, {
        method: 'PUT',
        body: JSON.stringify({ allocations }),
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
      title={copy.goals.allocationTitle}
      onClose={onClose}
      footer={
        <>
          <button className="p-button-secondary" type="button" onClick={onClose} disabled={pending}>
            {copy.common.cancel}
          </button>
          <button
            className="p-button"
            type="submit"
            form="planning-allocation-form"
            disabled={pending || eligible.length === 0}
          >
            {pending ? copy.common.saving : copy.common.save}
          </button>
        </>
      }
    >
      <form id="planning-allocation-form" className="p-stack" onSubmit={(event) => void submit(event)}>
        <p>{copy.goals.allocationHelp}</p>
        {eligible.length === 0 ? (
          <p className="p-muted">{copy.goals.noEligibleAccounts}</p>
        ) : (
          eligible.map((account) => (
            <Field key={account.id} label={`${account.name} · ${account.currency}`}>
              <input
                inputMode="decimal"
                type="number"
                min="0"
                step="0.01"
                value={amounts[account.id] ?? ''}
                onChange={(event) =>
                  setAmounts((current) => ({ ...current, [account.id]: event.target.value }))
                }
              />
            </Field>
          ))
        )}
        {requestError && <InlineError>{requestError}</InlineError>}
      </form>
    </Modal>
  );
}

function ArchiveGoalModal({
  locale,
  goal,
  onClose,
  onArchived,
}: {
  locale: PlatformPageProps['locale'];
  goal: Goal;
  onClose: () => void;
  onArchived: () => void;
}): ReactNode {
  const copy = planningCopy(locale);
  const [pending, setPending] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  async function archive(): Promise<void> {
    setPending(true);
    setRequestError(null);
    try {
      await request(`${planningPaths.goals}/${encodeURIComponent(goal.id)}`, z.unknown(), {
        method: 'DELETE',
      });
      onArchived();
    } catch (error) {
      setRequestError(errorMessage(error, locale));
    } finally {
      setPending(false);
    }
  }

  return (
    <Modal
      title={copy.goals.archiveTitle}
      onClose={onClose}
      destructive
      footer={
        <>
          <button className="p-button-secondary" type="button" onClick={onClose} disabled={pending}>
            {copy.common.cancel}
          </button>
          <button className="p-button-danger" type="button" onClick={() => void archive()} disabled={pending}>
            {copy.goals.confirmArchive}
          </button>
        </>
      }
    >
      <p>
        <strong>{goal.name}</strong>
      </p>
      <p>{copy.goals.archiveBody}</p>
      {requestError && <InlineError>{requestError}</InlineError>}
    </Modal>
  );
}

export function GoalsPage({
  locale,
  currency,
  query,
  revision,
  onChanged,
}: PlatformPageProps): ReactNode {
  const copy = planningCopy(locale);
  const [goalModal, setGoalModal] = useState<Goal | 'new' | null>(null);
  const [allocationGoal, setAllocationGoal] = useState<Goal | null>(null);
  const [archiveGoal, setArchiveGoal] = useState<Goal | null>(null);
  const selectedRecord = query.get('record_id');
  const resource = useResource<GoalData>(async () => {
    const [goals, accounts] = await Promise.all([
      request(planningPaths.goals, goalsResponseSchema),
      request(`${planningPaths.accounts}?limit=100&offset=0`, accountsResponseSchema),
    ]);
    return { goals: goals.items, accounts: accounts.items };
  }, [revision]);

  useEffect(() => {
    if (!resource.data || !selectedRecord) return;
    const row = document.getElementById(`goal-${selectedRecord}`);
    row?.scrollIntoView({ block: 'center' });
    row?.focus();
  }, [resource.data, selectedRecord]);

  function saved(): void {
    setGoalModal(null);
    setAllocationGoal(null);
    setArchiveGoal(null);
    resource.reload();
    onChanged();
  }

  if (!resource.data && resource.loading) return <LoadingState label={copy.common.loading} />;
  if (!resource.data && resource.error) {
    return (
      <ErrorState
        message={errorMessage(resource.error, locale)}
        retryLabel={copy.common.retry}
        onRetry={resource.reload}
      />
    );
  }
  if (!resource.data) return null;

  return (
    <div className="planning-page planning-goals-page">
      <PageHeader
        title={copy.goals.title}
        description={copy.goals.description}
        actions={
          <button className="p-button" type="button" onClick={() => setGoalModal('new')}>
            <Plus size={17} aria-hidden="true" />
            {copy.goals.add}
          </button>
        }
      />
      {resource.loading && <p className="p-muted" role="status">{copy.common.loading}</p>}
      {resource.data.goals.length === 0 ? (
        <Panel>
          <EmptyState
            title={copy.goals.empty}
            description={copy.goals.emptyDescription}
            action={
              <button className="p-button" type="button" onClick={() => setGoalModal('new')}>
                {copy.goals.add}
              </button>
            }
          />
        </Panel>
      ) : (
        <Panel aria-label={copy.goals.title}>
          <div className="p-ledger planning-goal-ledger">
            {resource.data.goals.map((goal) => {
              const target = Number(goal.target_amount);
              const allocated = Number(goal.allocated);
              const progress = target > 0 ? Math.min(100, Math.max(0, (allocated / target) * 100)) : 0;
              const underfunded = goal.allocations.some((allocation) => allocation.underfunded);
              return (
                <article
                  className={`p-ledger-row planning-goal-row${selectedRecord === goal.id ? ' planning-highlight' : ''}`}
                  id={`goal-${goal.id}`}
                  tabIndex={selectedRecord === goal.id ? -1 : undefined}
                  key={goal.id}
                >
                  <div className="p-row-main">
                    <div className="planning-goal-title">
                      <h2>{goal.name}</h2>
                      <span className="p-badge">{statusLabel(goal.status, locale)}</span>
                    </div>
                    <p className="p-muted">
                      {copy.goals.date}: {formatDate(goal.target_date, locale)}
                    </p>
                    <div className="planning-progress-group">
                      <div className="planning-progress-labels">
                        <span>{copy.goals.progress}</span>
                        <strong>{Math.round(progress)}%</strong>
                      </div>
                      <progress value={progress} max={100} aria-label={copy.goals.progress} />
                    </div>
                    {goal.allocations.length > 0 && (
                      <details className="planning-allocation-details">
                        <summary>
                          {copy.goals.allocationCount.replace('{count}', String(goal.allocations.length))}
                        </summary>
                        <ul>
                          {goal.allocations.map((allocation) => {
                            const account = resource.data?.accounts.find(
                              (item) => item.id === allocation.account_id,
                            );
                            return (
                              <li key={allocation.account_id}>
                                <div>
                                  <strong>{account?.name ?? copy.goals.accountUnavailable}</strong>
                                  <Money amount={allocation.amount} currency={goal.currency} locale={locale} />
                                </div>
                                {allocation.account_unavailable && (
                                  <span className="planning-warning-text">{copy.goals.accountUnavailable}</span>
                                )}
                                {allocation.underfunded && allocation.account_balance !== null && (
                                  <div className="planning-allocation-balance">
                                    <span>{copy.goals.currentBalance}</span>
                                    <Money
                                      amount={allocation.account_balance}
                                      currency={goal.currency}
                                      locale={locale}
                                    />
                                    {allocation.account_evidence && (
                                      <EvidenceLine evidence={allocation.account_evidence} locale={locale} />
                                    )}
                                  </div>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      </details>
                    )}
                    {underfunded && <p className="planning-warning-text">{copy.goals.underfunded}</p>}
                    <EvidenceLine evidence={goal.evidence} locale={locale} />
                  </div>
                  <div className="p-row-value planning-goal-values">
                    <dl>
                      <div>
                        <dt>{copy.goals.target}</dt>
                        <dd><Money amount={goal.target_amount} currency={goal.currency} locale={locale} /></dd>
                      </div>
                      <div>
                        <dt>{copy.goals.allocated}</dt>
                        <dd><Money amount={goal.allocated} currency={goal.currency} locale={locale} /></dd>
                      </div>
                      <div>
                        <dt>{copy.goals.remaining}</dt>
                        <dd><Money amount={goal.remaining} currency={goal.currency} locale={locale} /></dd>
                      </div>
                      <div>
                        <dt>{copy.goals.monthly}</dt>
                        <dd><Money amount={goal.monthly_contribution} currency={goal.currency} locale={locale} /></dd>
                      </div>
                    </dl>
                  </div>
                  <div className="p-row-actions planning-row-actions">
                    <button className="p-button-ghost" type="button" onClick={() => setGoalModal(goal)}>
                      <Pencil size={15} aria-hidden="true" />
                      {copy.common.edit}
                    </button>
                    <button className="p-button-secondary" type="button" onClick={() => setAllocationGoal(goal)}>
                      <WalletCards size={15} aria-hidden="true" />
                      {copy.goals.allocation}
                    </button>
                    <button className="p-button-ghost" type="button" onClick={() => setArchiveGoal(goal)}>
                      <Archive size={15} aria-hidden="true" />
                      {copy.common.archive}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </Panel>
      )}

      {goalModal && (
        <GoalModal
          locale={locale}
          defaultCurrency={currency}
          goal={goalModal === 'new' ? null : goalModal}
          onClose={() => setGoalModal(null)}
          onSaved={saved}
        />
      )}
      {allocationGoal && (
        <AllocationModal
          locale={locale}
          goal={allocationGoal}
          accounts={resource.data.accounts}
          onClose={() => setAllocationGoal(null)}
          onSaved={saved}
        />
      )}
      {archiveGoal && (
        <ArchiveGoalModal
          locale={locale}
          goal={archiveGoal}
          onClose={() => setArchiveGoal(null)}
          onArchived={saved}
        />
      )}
    </div>
  );
}
