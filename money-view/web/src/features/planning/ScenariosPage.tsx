import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { CopyPlus, Save } from 'lucide-react';
import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import type { Evidence, PlatformPageProps } from '../../platform/types';
import {
  EmptyState,
  EvidenceLine,
  Field,
  Money,
  PageHeader,
  Panel,
} from '../../platform/ui';
import { planningCopy, scenarioTemplateLabel } from './copy';
import {
  decimalSchema,
  planningPaths,
  scenarioCalculationSchema,
  scenarioComparisonSchema,
  scenarioInputsSchema,
  scenarioReceiptSchema,
  scenariosResponseSchema,
  scenarioTemplateIdSchema,
  scenarioTemplatesResponseSchema,
  type ScenarioCalculation,
  type ScenarioComparison,
  type ScenarioInputs,
  type ScenarioReceipt,
  type ScenarioResult,
  type ScenarioSummary,
  type ScenarioTemplate,
  type ScenarioTemplateId,
} from './contracts';
import { errorMessage, ErrorState, InlineError, LoadingState, signedAmountClass } from './shared';

type ScenarioData = {
  templates: ScenarioTemplate[];
  scenarios: ScenarioSummary[];
  scenarioTotal: number;
  scenarioLimit: number;
  scenarioOffset: number;
};

type ScenarioForm = {
  currency: string;
  initial_balance: string;
  monthly_contribution: string;
  monthly_withdrawal: string;
  horizon_years: string;
  annual_return_pct: string;
  inflation_pct: string;
  annual_fee_pct: string;
  contribution_start_month: string;
  contribution_end_month: string;
  withdrawal_start_month: string;
  withdrawal_end_month: string;
  timing: 'begin' | 'end';
};

type ScenarioErrors = Partial<Record<keyof ScenarioForm | 'name', string>>;

function formFromInputs(inputs: ScenarioInputs): ScenarioForm {
  return {
    currency: inputs.currency,
    initial_balance: inputs.initial_balance,
    monthly_contribution: inputs.monthly_contribution,
    monthly_withdrawal: inputs.monthly_withdrawal,
    horizon_years: String(inputs.horizon_years),
    annual_return_pct: inputs.annual_return_pct,
    inflation_pct: inputs.inflation_pct,
    annual_fee_pct: inputs.annual_fee_pct,
    contribution_start_month: String(inputs.contribution_start_month),
    contribution_end_month:
      inputs.contribution_end_month === null ? '' : String(inputs.contribution_end_month),
    withdrawal_start_month: String(inputs.withdrawal_start_month),
    withdrawal_end_month:
      inputs.withdrawal_end_month === null ? '' : String(inputs.withdrawal_end_month),
    timing: inputs.timing,
  };
}

function validateForm(
  form: ScenarioForm,
  name: string,
  invalidMessage: string,
  requiredMessage: string,
): { inputs: ScenarioInputs | null; errors: ScenarioErrors } {
  const errors: ScenarioErrors = {};
  if (name.trim() === '') errors.name = requiredMessage;
  const decimalKeys: Array<keyof Pick<
    ScenarioForm,
    | 'initial_balance'
    | 'monthly_contribution'
    | 'monthly_withdrawal'
    | 'annual_return_pct'
    | 'inflation_pct'
    | 'annual_fee_pct'
  >> = [
    'initial_balance',
    'monthly_contribution',
    'monthly_withdrawal',
    'annual_return_pct',
    'inflation_pct',
    'annual_fee_pct',
  ];
  decimalKeys.forEach((key) => {
    if (!decimalSchema.safeParse(form[key]).success) errors[key] = invalidMessage;
  });
  const integerKeys: Array<keyof Pick<
    ScenarioForm,
    | 'horizon_years'
    | 'contribution_start_month'
    | 'withdrawal_start_month'
  >> = ['horizon_years', 'contribution_start_month', 'withdrawal_start_month'];
  integerKeys.forEach((key) => {
    if (!Number.isInteger(Number(form[key]))) errors[key] = invalidMessage;
  });
  for (const key of ['contribution_end_month', 'withdrawal_end_month'] as const) {
    if (form[key] !== '' && !Number.isInteger(Number(form[key]))) errors[key] = invalidMessage;
  }
  if (form.currency.trim().length !== 3) errors.currency = requiredMessage;
  if (Object.keys(errors).length > 0) return { inputs: null, errors };

  const parsed = scenarioInputsSchema.safeParse({
    currency: form.currency.toUpperCase(),
    initial_balance: form.initial_balance,
    monthly_contribution: form.monthly_contribution,
    monthly_withdrawal: form.monthly_withdrawal,
    horizon_years: Number(form.horizon_years),
    annual_return_pct: form.annual_return_pct,
    inflation_pct: form.inflation_pct,
    annual_fee_pct: form.annual_fee_pct,
    contribution_start_month: Number(form.contribution_start_month),
    contribution_end_month:
      form.contribution_end_month === '' ? null : Number(form.contribution_end_month),
    withdrawal_start_month: Number(form.withdrawal_start_month),
    withdrawal_end_month:
      form.withdrawal_end_month === '' ? null : Number(form.withdrawal_end_month),
    timing: form.timing,
  });
  if (!parsed.success) {
    parsed.error.issues.forEach((issue) => {
      const key = String(issue.path[0]) as keyof ScenarioForm;
      errors[key] = invalidMessage;
    });
    return { inputs: null, errors };
  }
  const numeric = parsed.data;
  if (
    Number(numeric.initial_balance) < 0 ||
    Number(numeric.monthly_contribution) < 0 ||
    Number(numeric.monthly_withdrawal) < 0 ||
    Number(numeric.initial_balance) > 1e12 ||
    Number(numeric.monthly_contribution) > 1e12 ||
    Number(numeric.monthly_withdrawal) > 1e12
  ) {
    errors.initial_balance = invalidMessage;
  }
  if (Number(numeric.annual_return_pct) < -99 || Number(numeric.annual_return_pct) > 100) {
    errors.annual_return_pct = invalidMessage;
  }
  if (Number(numeric.inflation_pct) < -99 || Number(numeric.inflation_pct) > 100) {
    errors.inflation_pct = invalidMessage;
  }
  if (Number(numeric.annual_fee_pct) < 0 || Number(numeric.annual_fee_pct) > 20) {
    errors.annual_fee_pct = invalidMessage;
  }
  if (
    numeric.contribution_end_month !== null &&
    numeric.contribution_end_month < numeric.contribution_start_month
  ) {
    errors.contribution_end_month = invalidMessage;
  }
  if (
    numeric.withdrawal_end_month !== null &&
    numeric.withdrawal_end_month < numeric.withdrawal_start_month
  ) {
    errors.withdrawal_end_month = invalidMessage;
  }
  return Object.keys(errors).length > 0
    ? { inputs: null, errors }
    : { inputs: numeric, errors: {} };
}

function sumDecimals(values: string[]): string {
  const scale = Math.max(0, ...values.map((value) => value.split('.')[1]?.length ?? 0));
  const factor = 10n ** BigInt(scale);
  const total = values.reduce((sum, value) => {
    const negative = value.startsWith('-');
    const unsigned = negative ? value.slice(1) : value;
    const [whole, fraction = ''] = unsigned.split('.');
    const units = BigInt(whole || '0') * factor + BigInt(fraction.padEnd(scale, '0') || '0');
    return sum + (negative ? -units : units);
  }, 0n);
  const negative = total < 0n;
  const absolute = negative ? -total : total;
  if (scale === 0) return `${negative ? '-' : ''}${absolute}`;
  const whole = absolute / factor;
  const fraction = String(absolute % factor).padStart(scale, '0').replace(/0+$/, '');
  return `${negative ? '-' : ''}${whole}${fraction ? `.${fraction}` : ''}`;
}

function ScenarioResultView({
  locale,
  result,
  evidence,
}: {
  locale: PlatformPageProps['locale'];
  result: ScenarioResult;
  evidence: Evidence;
}): ReactNode {
  const copy = planningCopy(locale);
  const shortfall = sumDecimals(result.months.map((month) => month.unfunded_withdrawal));
  return (
    <section className="planning-scenario-result" aria-labelledby="scenario-result-title">
      <div className="planning-section-heading">
        <div>
          <h2 id="scenario-result-title">{copy.scenarios.result}</h2>
          <p className="p-muted">{copy.scenarios.illustrative}</p>
        </div>
      </div>
      <div className="p-metrics planning-scenario-metrics">
        <div className="p-metric planning-primary-metric">
          <span>{copy.scenarios.endingBalance}</span>
          <strong><Money amount={result.ending_balance} currency={result.currency} locale={locale} /></strong>
        </div>
        <div className="p-metric">
          <span>{copy.scenarios.realEndingBalance}</span>
          <strong><Money amount={result.real_ending_balance} currency={result.currency} locale={locale} /></strong>
        </div>
        <div className="p-metric">
          <span>{copy.scenarios.contributions}</span>
          <strong><Money amount={result.total_contributions} currency={result.currency} locale={locale} /></strong>
        </div>
        <div className="p-metric">
          <span>{copy.scenarios.withdrawals}</span>
          <strong><Money amount={result.total_withdrawals} currency={result.currency} locale={locale} /></strong>
        </div>
        <div className="p-metric">
          <span>{copy.scenarios.fees}</span>
          <strong><Money amount={result.total_fees} currency={result.currency} locale={locale} /></strong>
        </div>
        <div className="p-metric">
          <span>{copy.scenarios.shortfall}</span>
          <strong><Money amount={shortfall} currency={result.currency} locale={locale} /></strong>
        </div>
      </div>
      <p className="planning-depletion">
        <strong>{copy.scenarios.depletion}:</strong>{' '}
        {result.depletion_month === null ? copy.scenarios.noDepletion : result.depletion_month}
      </p>
      <EvidenceLine evidence={evidence} locale={locale} />
      <details className="planning-yearly-results">
        <summary>{copy.scenarios.yearly}</summary>
        <div className="p-table-wrap">
          <table className="p-table planning-table">
            <thead>
              <tr>
                <th scope="col">{copy.scenarios.year}</th>
                <th scope="col">{copy.scenarios.nominal}</th>
                <th scope="col">{copy.scenarios.real}</th>
              </tr>
            </thead>
            <tbody>
              {result.years.map((year) => (
                <tr key={year.year}>
                  <td data-label={copy.scenarios.year}>{year.year}</td>
                  <td data-label={copy.scenarios.nominal}>
                    <Money amount={year.balance} currency={result.currency} locale={locale} />
                  </td>
                  <td data-label={copy.scenarios.real}>
                    <Money amount={year.real_balance} currency={result.currency} locale={locale} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}

function ComparisonView({
  locale,
  comparison,
}: {
  locale: PlatformPageProps['locale'];
  comparison: ScenarioComparison;
}): ReactNode {
  const copy = planningCopy(locale);
  return (
    <div className="planning-comparison-result" aria-live="polite">
      <div className="planning-comparison-columns">
        {[
          { label: copy.scenarios.before, receipt: comparison.before },
          { label: copy.scenarios.after, receipt: comparison.after },
        ].map(({ label, receipt }) => (
          <section key={`${label}:${receipt.id}`}>
            <span className="p-eyebrow">{label}</span>
            <h3>{receipt.name}</h3>
            <p className="planning-compare-value">
              <Money amount={receipt.result.ending_balance} currency={receipt.result.currency} locale={locale} />
            </p>
            <p className="p-muted">{copy.scenarios.immutable}</p>
            <EvidenceLine evidence={receipt.evidence} locale={locale} />
          </section>
        ))}
      </div>
      <div className="planning-delta">
        <span>{copy.scenarios.change}</span>
        <strong className={signedAmountClass(comparison.delta_ending_balance)}>
          <Money
            amount={comparison.delta_ending_balance}
            currency={comparison.before.result.currency}
            locale={locale}
          />
        </strong>
      </div>
    </div>
  );
}

export function ScenariosPage({
  locale,
  currency,
  query,
  revision,
  onNavigate,
  onChanged,
}: PlatformPageProps): ReactNode {
  const copy = planningCopy(locale);
  const requestedTemplate = scenarioTemplateIdSchema.safeParse(query.get('template'));
  const [selectedTemplate, setSelectedTemplate] = useState<ScenarioTemplateId | null>(
    requestedTemplate.success ? requestedTemplate.data : null,
  );
  const [name, setName] = useState('');
  const [form, setForm] = useState<ScenarioForm | null>(null);
  const [errors, setErrors] = useState<ScenarioErrors>({});
  const [calculation, setCalculation] = useState<ScenarioCalculation | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pending, setPending] = useState<'calculate' | 'save' | 'compare' | 'load' | null>(null);
  const [savedNotice, setSavedNotice] = useState(false);
  const [beforeId, setBeforeId] = useState('');
  const [afterId, setAfterId] = useState('');
  const [comparison, setComparison] = useState<ScenarioComparison | null>(null);
  const [scenarioOffset, setScenarioOffset] = useState(0);
  const resource = useResource<ScenarioData>(async () => {
    const [templates, scenarios] = await Promise.all([
      request(
        `${planningPaths.scenarioTemplates}?currency=${encodeURIComponent(currency)}`,
        scenarioTemplatesResponseSchema,
      ),
      request(
        `${planningPaths.scenarios}?limit=20&offset=${scenarioOffset}`,
        scenariosResponseSchema,
      ),
    ]);
    return {
      templates: templates.items,
      scenarios: scenarios.items,
      scenarioTotal: scenarios.total,
      scenarioLimit: scenarios.limit,
      scenarioOffset: scenarios.offset,
    };
  }, [currency, revision, scenarioOffset]);

  useEffect(() => {
    if (!resource.data || form) return;
    const template =
      resource.data.templates.find((item) => item.id === selectedTemplate) ?? resource.data.templates[0];
    if (!template) return;
    setSelectedTemplate(template.id);
    setForm(formFromInputs(template.inputs));
  }, [resource.data, form, selectedTemplate]);

  useEffect(() => {
    if (!resource.data || resource.data.scenarios.length < 2) return;
    const ids = new Set(resource.data.scenarios.map((scenario) => scenario.id));
    setBeforeId((current) => (ids.has(current) ? current : resource.data?.scenarios[1]?.id || ''));
    setAfterId((current) => (ids.has(current) ? current : resource.data?.scenarios[0]?.id || ''));
  }, [resource.data]);

  function updateForm<K extends keyof ScenarioForm>(key: K, value: ScenarioForm[K]): void {
    setForm((current) => (current ? { ...current, [key]: value } : current));
    setSavedNotice(false);
  }

  function chooseTemplate(template: ScenarioTemplate): void {
    setSelectedTemplate(template.id);
    setForm(formFromInputs(template.inputs));
    setCalculation(null);
    setComparison(null);
    setErrors({});
    setActionError(null);
    setSavedNotice(false);
    onNavigate('scenarios', { template: template.id });
  }

  function applyReceipt(receipt: ScenarioReceipt): void {
    setSelectedTemplate(receipt.template);
    setName(`${receipt.name}`);
    setForm(formFromInputs(receipt.inputs));
    setCalculation({ ...receipt.result, evidence: receipt.evidence });
    setErrors({});
    setActionError(null);
    setSavedNotice(false);
    onNavigate('scenarios', { template: receipt.template });
    document.querySelector<HTMLElement>('.planning-scenario-workspace h2')?.focus();
  }

  async function useReceipt(receipt: ScenarioSummary): Promise<void> {
    setPending('load');
    setActionError(null);
    try {
      const fullReceipt = await request(
        `${planningPaths.scenarios}/${encodeURIComponent(receipt.id)}`,
        scenarioReceiptSchema,
      );
      applyReceipt(fullReceipt);
    } catch (error) {
      setActionError(errorMessage(error, locale));
    } finally {
      setPending(null);
    }
  }

  function payload(): { name: string; template: ScenarioTemplateId; inputs: ScenarioInputs } | null {
    if (!form || !selectedTemplate) return null;
    const validated = validateForm(
      form,
      name,
      copy.errors.invalidNumber,
      copy.errors.required,
    );
    setErrors(validated.errors);
    if (!validated.inputs) return null;
    return { name: name.trim(), template: selectedTemplate, inputs: validated.inputs };
  }

  async function calculate(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const body = payload();
    if (!body) return;
    setPending('calculate');
    setActionError(null);
    setSavedNotice(false);
    try {
      setCalculation(
        await request(planningPaths.scenarioCalculate, scenarioCalculationSchema, {
          method: 'POST',
          body: JSON.stringify(body),
        }),
      );
    } catch (error) {
      setActionError(errorMessage(error, locale));
    } finally {
      setPending(null);
    }
  }

  async function save(): Promise<void> {
    const body = payload();
    if (!body) return;
    setPending('save');
    setActionError(null);
    setSavedNotice(false);
    try {
      const receipt = await request(planningPaths.scenarios, scenarioReceiptSchema, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setCalculation({ ...receipt.result, evidence: receipt.evidence });
      setSavedNotice(true);
      setScenarioOffset(0);
      resource.reload();
      onChanged();
    } catch (error) {
      setActionError(errorMessage(error, locale));
    } finally {
      setPending(null);
    }
  }

  async function compare(): Promise<void> {
    if (!beforeId || !afterId || beforeId === afterId) {
      setActionError(copy.scenarios.chooseTwo);
      return;
    }
    setPending('compare');
    setActionError(null);
    try {
      const parameters = new URLSearchParams({ before_id: beforeId, after_id: afterId });
      setComparison(
        await request(`${planningPaths.scenarioCompare}?${parameters.toString()}`, scenarioComparisonSchema),
      );
    } catch (error) {
      setActionError(errorMessage(error, locale));
    } finally {
      setPending(null);
    }
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
    <div className="planning-page planning-scenarios-page">
      <PageHeader title={copy.scenarios.title} description={copy.scenarios.description} />
      {resource.loading && <p className="p-muted" role="status">{copy.common.loading}</p>}
      <nav className="p-tabs planning-template-tabs" aria-label={copy.scenarios.template}>
        {resource.data.templates.map((template) => (
          <button
            type="button"
            key={template.id}
            aria-pressed={selectedTemplate === template.id}
            onClick={() => chooseTemplate(template)}
          >
            {scenarioTemplateLabel(template.id, locale)}
          </button>
        ))}
      </nav>

      {form && selectedTemplate ? (
        <Panel className="planning-scenario-workspace">
          <div className="planning-section-heading">
            <div>
              <h2 tabIndex={-1}>{scenarioTemplateLabel(selectedTemplate, locale)}</h2>
              <p className="p-muted">{copy.scenarios.assumptions}</p>
            </div>
          </div>
          <form className="p-stack" onSubmit={(event) => void calculate(event)}>
            <Field label={copy.scenarios.name} error={errors.name}>
              <input
                value={name}
                maxLength={120}
                placeholder={copy.scenarios.namePlaceholder}
                onChange={(event) => {
                  setName(event.target.value);
                  setSavedNotice(false);
                }}
              />
            </Field>
            <div className="p-form-grid planning-scenario-grid">
              <Field label={copy.scenarios.currency} error={errors.currency}>
                <input
                  maxLength={3}
                  value={form.currency}
                  onChange={(event) => updateForm('currency', event.target.value.toUpperCase())}
                />
              </Field>
              <Field label={copy.scenarios.initialBalance} error={errors.initial_balance}>
                <input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={form.initial_balance}
                  onChange={(event) => updateForm('initial_balance', event.target.value)}
                />
              </Field>
              <Field label={copy.scenarios.contribution} error={errors.monthly_contribution}>
                <input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={form.monthly_contribution}
                  onChange={(event) => updateForm('monthly_contribution', event.target.value)}
                />
              </Field>
              <Field label={copy.scenarios.withdrawal} error={errors.monthly_withdrawal}>
                <input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={form.monthly_withdrawal}
                  onChange={(event) => updateForm('monthly_withdrawal', event.target.value)}
                />
              </Field>
              <Field label={copy.scenarios.horizon} error={errors.horizon_years}>
                <input
                  type="number"
                  inputMode="numeric"
                  min="1"
                  max="100"
                  value={form.horizon_years}
                  onChange={(event) => updateForm('horizon_years', event.target.value)}
                />
              </Field>
              <Field label={copy.scenarios.returnRate} error={errors.annual_return_pct}>
                <input
                  type="number"
                  inputMode="decimal"
                  min="-99"
                  max="100"
                  step="0.01"
                  value={form.annual_return_pct}
                  onChange={(event) => updateForm('annual_return_pct', event.target.value)}
                />
              </Field>
              <Field label={copy.scenarios.inflation} error={errors.inflation_pct}>
                <input
                  type="number"
                  inputMode="decimal"
                  min="-99"
                  max="100"
                  step="0.01"
                  value={form.inflation_pct}
                  onChange={(event) => updateForm('inflation_pct', event.target.value)}
                />
              </Field>
              <Field label={copy.scenarios.fee} error={errors.annual_fee_pct}>
                <input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  max="20"
                  step="0.01"
                  value={form.annual_fee_pct}
                  onChange={(event) => updateForm('annual_fee_pct', event.target.value)}
                />
              </Field>
              <Field label={copy.scenarios.contributionStart} error={errors.contribution_start_month}>
                <input
                  type="number"
                  inputMode="numeric"
                  min="1"
                  max="1200"
                  value={form.contribution_start_month}
                  onChange={(event) => updateForm('contribution_start_month', event.target.value)}
                />
              </Field>
              <Field
                label={copy.scenarios.contributionEnd}
                help={copy.scenarios.optionalEnd}
                error={errors.contribution_end_month}
              >
                <input
                  type="number"
                  inputMode="numeric"
                  min="1"
                  max="1200"
                  value={form.contribution_end_month}
                  onChange={(event) => updateForm('contribution_end_month', event.target.value)}
                />
              </Field>
              <Field label={copy.scenarios.withdrawalStart} error={errors.withdrawal_start_month}>
                <input
                  type="number"
                  inputMode="numeric"
                  min="1"
                  max="1200"
                  value={form.withdrawal_start_month}
                  onChange={(event) => updateForm('withdrawal_start_month', event.target.value)}
                />
              </Field>
              <Field
                label={copy.scenarios.withdrawalEnd}
                help={copy.scenarios.optionalEnd}
                error={errors.withdrawal_end_month}
              >
                <input
                  type="number"
                  inputMode="numeric"
                  min="1"
                  max="1200"
                  value={form.withdrawal_end_month}
                  onChange={(event) => updateForm('withdrawal_end_month', event.target.value)}
                />
              </Field>
              <Field label={copy.scenarios.timing} error={errors.timing}>
                <select
                  value={form.timing}
                  onChange={(event) => updateForm('timing', event.target.value as 'begin' | 'end')}
                >
                  <option value="begin">{copy.scenarios.timingBegin}</option>
                  <option value="end">{copy.scenarios.timingEnd}</option>
                </select>
              </Field>
            </div>
            <p className="p-muted">{copy.scenarios.illustrative}</p>
            {actionError && <InlineError>{actionError}</InlineError>}
            {savedNotice && <p className="p-success" role="status">{copy.scenarios.savedSuccess}</p>}
            <div className="p-actions">
              <button className="p-button-secondary" type="submit" disabled={pending !== null}>
                {pending === 'calculate' ? copy.scenarios.calculating : copy.scenarios.calculate}
              </button>
              <button className="p-button" type="button" disabled={pending !== null} onClick={() => void save()}>
                <Save size={17} aria-hidden="true" />
                {pending === 'save' ? copy.common.saving : copy.scenarios.save}
              </button>
            </div>
          </form>
          {calculation && (
            <ScenarioResultView locale={locale} result={calculation} evidence={calculation.evidence} />
          )}
        </Panel>
      ) : (
        <Panel>
          <EmptyState title={copy.scenarios.template} description={copy.scenarios.description} />
        </Panel>
      )}

      <Panel aria-labelledby="saved-scenarios-title">
        <div className="planning-section-heading">
          <div>
            <h2 id="saved-scenarios-title">{copy.scenarios.saved}</h2>
            <p className="p-muted">{copy.scenarios.immutable}</p>
          </div>
        </div>
        {resource.data.scenarios.length === 0 ? (
          <EmptyState title={copy.scenarios.empty} description={copy.scenarios.emptyDescription} />
        ) : (
          <div className="p-table-wrap planning-table-wrap">
            <table className="p-table planning-table">
              <thead>
                <tr>
                  <th scope="col">{copy.scenarios.name}</th>
                  <th scope="col">{copy.scenarios.template}</th>
                  <th scope="col">{copy.scenarios.endingBalance}</th>
                  <th scope="col">{copy.budgets.actions}</th>
                </tr>
              </thead>
              <tbody>
                {resource.data.scenarios.map((receipt) => (
                  <tr key={receipt.id}>
                    <td data-label={copy.scenarios.name}>
                      <strong>{receipt.name}</strong>
                      <EvidenceLine evidence={receipt.evidence} locale={locale} />
                    </td>
                    <td data-label={copy.scenarios.template}>
                      {scenarioTemplateLabel(receipt.template, locale)}
                    </td>
                    <td data-label={copy.scenarios.endingBalance}>
                      <Money
                        amount={receipt.result.ending_balance}
                        currency={receipt.result.currency}
                        locale={locale}
                      />
                    </td>
                    <td data-label={copy.budgets.actions}>
                      <button
                        className="p-button-ghost"
                        type="button"
                        disabled={pending !== null}
                        onClick={() => void useReceipt(receipt)}
                      >
                        <CopyPlus size={15} aria-hidden="true" />
                        {copy.scenarios.newVersion}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {resource.data.scenarioTotal > resource.data.scenarioLimit && (
          <nav className="p-pagination" aria-label={copy.scenarios.saved}>
            <button
              className="p-button-secondary"
              type="button"
              disabled={resource.data.scenarioOffset === 0 || resource.loading}
              onClick={() =>
                setScenarioOffset(Math.max(0, resource.data!.scenarioOffset - resource.data!.scenarioLimit))
              }
            >
              {copy.scenarios.previousPage}
            </button>
            <span>
              {copy.scenarios.pageCount
                .replace('{start}', String(resource.data.scenarioOffset + 1))
                .replace(
                  '{end}',
                  String(
                    Math.min(
                      resource.data.scenarioTotal,
                      resource.data.scenarioOffset + resource.data.scenarios.length,
                    ),
                  ),
                )
                .replace('{total}', String(resource.data.scenarioTotal))}
            </span>
            <button
              className="p-button-secondary"
              type="button"
              disabled={
                resource.loading ||
                resource.data.scenarioOffset + resource.data.scenarioLimit >= resource.data.scenarioTotal
              }
              onClick={() => setScenarioOffset(resource.data!.scenarioOffset + resource.data!.scenarioLimit)}
            >
              {copy.scenarios.nextPage}
            </button>
          </nav>
        )}
      </Panel>

      {resource.data.scenarios.length >= 2 && (
        <Panel className="planning-compare-panel" aria-labelledby="scenario-compare-title">
          <div className="planning-section-heading">
            <div>
              <h2 id="scenario-compare-title">{copy.scenarios.compare}</h2>
              <p className="p-muted">{copy.scenarios.chooseTwo}</p>
            </div>
          </div>
          <div className="planning-compare-controls">
            <Field label={copy.scenarios.before}>
              <select value={beforeId} onChange={(event) => setBeforeId(event.target.value)}>
                {resource.data.scenarios.map((receipt) => (
                  <option key={receipt.id} value={receipt.id}>
                    {receipt.name} · {receipt.result.currency}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={copy.scenarios.after}>
              <select value={afterId} onChange={(event) => setAfterId(event.target.value)}>
                {resource.data.scenarios.map((receipt) => (
                  <option key={receipt.id} value={receipt.id}>
                    {receipt.name} · {receipt.result.currency}
                  </option>
                ))}
              </select>
            </Field>
            <button className="p-button-secondary" type="button" disabled={pending !== null} onClick={() => void compare()}>
              {pending === 'compare' ? copy.common.loading : copy.scenarios.runCompare}
            </button>
          </div>
          {comparison && <ComparisonView locale={locale} comparison={comparison} />}
        </Panel>
      )}
    </div>
  );
}
