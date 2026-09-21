import { useState,type FormEvent } from 'react';
import { z } from 'zod';
import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import { PageHeader,Panel,Field,EvidenceLine,Money,EmptyState } from '../../platform/ui';
import { evidenceSchema,type PlatformPageProps } from '../../platform/types';
import { text,dateLabel,today,currencies,EditDialog,ErrorMessage,Loading,type InputSpec } from './shared';
const accountSchema=z.object({ id: z.string(),name: z.string(),currency: z.string(),balance: z.string(),credit_limit: z.string(),apr_pct: z.string(),minimum_payment: z.string(),evidence: evidenceSchema });
const creditSchema=z.object({ accounts: z.array(accountSchema),report: z.object({ score: z.number(),scale_min: z.number(),scale_max: z.number(),history: z.array(z.object({ as_of: z.string(),score: z.number() })),factors: z.array(z.object({ code: z.string(),impact: z.string() })),evidence: evidenceSchema }).nullable(),utilization: z.array(z.object({ currency: z.string(),balance: z.string(),credit_limit: z.string(),utilization_pct: z.string().nullable(),evidence: evidenceSchema })) });
const payoffSchema=z.object({ account_id: z.string(),currency: z.string(),monthly_payment: z.string(),status: z.string(),months: z.number().nullable(),total_interest: z.string(),total_paid: z.string(),formula: z.string(),assumptions: z.array(z.string()),evidence: evidenceSchema });
type Account=z.infer<typeof accountSchema>;
const factorLabels: Record<string,[
  string,
  string
]>={ payment_history: ['Historial de pagos','Payment history'],utilization: ['Uso del crédito','Credit utilization'],credit_utilization: ['Uso del crédito','Credit utilization'],credit_age: ['Antigüedad del crédito','Credit age'],credit_mix: ['Tipos de crédito','Credit mix'],recent_inquiries: ['Consultas recientes','Recent inquiries'],on_time_payments: ['Pagos a tiempo','On-time payments'],revolving_utilization: ['Uso del crédito rotativo','Revolving utilization'] };
export function CreditPage(props: PlatformPageProps) {
  const { locale,revision,onChanged,currency }=props;
  const t=(es: string,en: string) => text(locale,es,en);
  const resource=useResource(() => request('/credit',creditSchema),[revision]);
  const [edit,setEdit]=useState<Account|'new'|null>(null);
  const [accountId,setAccountId]=useState('');
  const [extra,setExtra]=useState('50');
  const [payoff,setPayoff]=useState<z.infer<typeof payoffSchema>|null>(null);
  const [pending,setPending]=useState(false);
  const [error,setError]=useState<unknown>(null);
  const changed=() => { resource.reload(); onChanged(); setPayoff(null); };
  const data=resource.data;
  const selected=data?.accounts.find(a => a.id===(accountId||data.accounts[0]?.id));
  async function calculate(e: FormEvent) {
    e.preventDefault(); if(!selected)
      return; setPending(true); setError(null); setPayoff(null); try {
        setPayoff(await request('/credit/payoff',payoffSchema,{ method: 'POST',body: JSON.stringify({ account_id: selected.id,extra_monthly_payment: extra }) }));
      }
    catch(e) {
      setError(e);
    }
    finally {
      setPending(false);
    }
  }
  const current=edit&&edit!=='new'? edit:null;
  const fields: InputSpec[]=[{ name: 'name',es: 'Nombre de la deuda',en: 'Debt name',value: current?.name },{ name: 'currency',es: 'Moneda',en: 'Currency',options: currencies,value: current?.currency||currency },{ name: 'balance',es: 'Saldo pendiente',en: 'Outstanding balance',type: 'number',min: '0',step: 'any',value: current?.balance },{ name: 'credit_limit',es: 'Límite de crédito',en: 'Credit limit',type: 'number',min: '0',step: 'any',value: current?.credit_limit },{ name: 'apr_pct',es: 'Tasa anual (%)',en: 'Annual rate (%)',type: 'number',min: '0',max: '1000',step: 'any',value: current?.apr_pct },{ name: 'minimum_payment',es: 'Pago mensual fijo',en: 'Fixed monthly payment',type: 'number',min: '0',step: 'any',value: current?.minimum_payment },{ name: 'as_of',es: 'Fecha de los valores',en: 'Values as of',type: 'date',value: current?.evidence.as_of.slice(0,10)||today() }];
  return <div className="p-stack services-page">
    <PageHeader eyebrow={t('CRÉDITO','CREDIT')} title={t('Entiende tu deuda.','Understand your debt.')} description={t('Revisa tus saldos y calcula qué cambia con un pago adicional.','Review balances and calculate what changes with an extra payment.')} actions={
      <button className="p-button" onClick={() => setEdit('new')}>
        {t('Añadir deuda','Add debt')}
      </button>
    } />
    <Loading locale={locale} {...resource} retry={resource.reload} />

    {data&&<>
      <div className="services-columns">
        <Panel className="services-score">
          <span className="p-badge">
            {t('REPORTE SINTÉTICO','SYNTHETIC REPORT')}
          </span>
          {data.report? <>
            <p className="services-big-number">
              {data.report.score}
            </p>
            <p>
              {t('Escala ilustrativa','Illustrative scale')} {data.report.scale_min}–{data.report.scale_max}
            </p>
            <EvidenceLine locale={locale} evidence={data.report.evidence} />
            <p className="p-muted">
              {t('No es un reporte de una agencia de crédito. Tus cambios no modifican este ejemplo.','This is not a credit bureau report. Your edits do not change this example.')}
            </p>
            <div className="services-history" aria-label={t('Historial sintético de puntaje','Synthetic score history')}>
              {data.report.history.map(h =>
                <div key={h.as_of}>
                  <span className="services-history-bar" style={{ height: `${Math.max(8,(h.score-data.report!.scale_min)/(data.report!.scale_max-data.report!.scale_min)*100)}px` }} />
                  <strong>
                    {h.score}
                  </strong>
                  <small>
                    {dateLabel(h.as_of,locale)}
                  </small>
                </div>
              )}
            </div>
          </>:
            <EmptyState title={t('Sin reporte de ejemplo','No sample report')} />
          }
        </Panel>
        <Panel>
          <h2>
            {t('Qué muestra el ejemplo','What the example shows')}
          </h2>
          {data.report?.factors.map(f =>
            <div className="p-ledger-row" key={f.code}>
              <span>
                {factorLabels[f.code]?.[locale==='en'? 1:0]||t('Factor ilustrativo','Illustrative factor')}
              </span>
              <span className="p-badge">
                {({ positive: t('Positivo','Positive'),negative: t('Por revisar','Needs review'),neutral: t('Neutral','Neutral'),mixed: t('Mixto','Mixed'),high: t('Alto','High'),medium: t('Medio','Medium'),low: t('Bajo','Low') })[f.impact]||t('Ilustrativo','Illustrative')}
              </span>
            </div>
          )}
          <h3>
            {t('Uso del crédito registrado','Recorded credit utilization')}
          </h3>
          {data.utilization.map(u =>
            <div className="services-detail-row" key={u.currency}>
              <strong>
                {u.currency} · {u.utilization_pct===null? t('Sin límite registrado','No recorded limit'):`${u.utilization_pct}%`}
              </strong>
              <span>
                <Money locale={locale} currency={u.currency} amount={u.balance} />
                /
                <Money locale={locale} currency={u.currency} amount={u.credit_limit} />
              </span>
              <EvidenceLine evidence={u.evidence} locale={locale} />
            </div>
          )}
        </Panel>
      </div>


      <Panel>
        <h2>
          {t('Tus deudas, una por una','Your debts, one by one')}
        </h2>
        {data.accounts.length===0?
          <EmptyState title={t('Añade tu primera deuda','Add your first debt')} description={t('Registra saldo, tasa y pago para calcular un escenario.','Record a balance, rate and payment to calculate a scenario.')} />
          :data.accounts.map(a =>
            <article className="services-account" key={a.id}>
              <div className="p-toolbar">
                <h3>
                  {a.name}
                </h3>
                <button className="p-button-ghost" onClick={() => setEdit(a)}>
                  {t('Editar','Edit')}
                </button>
              </div>
              <dl className="services-facts">
                <div>
                  <dt>
                    {t('Saldo','Balance')}
                  </dt>
                  <dd>
                    <Money amount={a.balance} currency={a.currency} locale={locale} />
                  </dd>
                </div>
                <div>
                  <dt>
                    {t('Límite','Limit')}
                  </dt>
                  <dd>
                    <Money amount={a.credit_limit} currency={a.currency} locale={locale} />
                  </dd>
                </div>
                <div>
                  <dt>
                    {t('Tasa anual','Annual rate')}
                  </dt>
                  <dd>
                    {a.apr_pct}%
                  </dd>
                </div>
                <div>
                  <dt>
                    {t('Pago mensual','Monthly payment')}
                  </dt>
                  <dd>
                    <Money amount={a.minimum_payment} currency={a.currency} locale={locale} />
                  </dd>
                </div>
              </dl>
              <EvidenceLine evidence={a.evidence} locale={locale} />
            </article>
          )}
      </Panel>


      <Panel>
        <h2>
          {t('Un pago adicional, otro escenario','An extra payment, another scenario')}
        </h2>
        <p className="p-muted">
          {t('Interés mensual sobre el saldo, con pago fijo. Sin nuevas compras, comisiones ni cambios de tasa.','Monthly interest on the balance, with a fixed payment. No new purchases, fees or rate changes.')}
        </p>
        <form className="p-form-grid" onSubmit={calculate}>
          <Field label={t('Deuda','Debt')}>
            <select value={selected?.id||''} required onChange={e => { setAccountId(e.target.value); setPayoff(null); }}>
              <option value="" disabled>
                {t('Elige una deuda','Choose a debt')}
              </option>
              {data.accounts.map(a =>
                <option value={a.id} key={a.id}>
                  {a.name} · {a.currency}
                </option>
              )}
            </select>
          </Field>
          <Field label={t('Pago adicional mensual','Extra monthly payment')}>
            <input type="number" min="0" step="any" value={extra} onChange={e => { setExtra(e.target.value); setPayoff(null); }} required />
          </Field>
          <button className="p-button" disabled={pending||!selected}>
            {pending? t('Calculando…','Calculating…'):t('Calcular escenario','Calculate scenario')}
          </button>
        </form>
        <ErrorMessage error={error} locale={locale} />
        {payoff&&
          <div className="services-result" role="status">
            <h3>
              {payoff.status==='paid_off'? t('Escenario de saldo liquidado','Balance payoff scenario'):t('El saldo no se liquida en este escenario','The balance is not paid off in this scenario')}
            </h3>
            <dl className="services-facts">
              <div>
                <dt>
                  {t('Meses','Months')}
                </dt>
                <dd>
                  {payoff.months??t('Sin resultado','Unresolved')}
                </dd>
              </div>
              <div>
                <dt>
                  {t('Pago mensual','Monthly payment')}
                </dt>
                <dd>
                  <Money amount={payoff.monthly_payment} currency={payoff.currency} locale={locale} />
                </dd>
              </div>
              <div>
                <dt>
                  {t('Interés calculado','Calculated interest')}
                </dt>
                <dd>
                  <Money amount={payoff.total_interest} currency={payoff.currency} locale={locale} />
                </dd>
              </div>
              <div>
                <dt>
                  {t('Total calculado','Calculated total')}
                </dt>
                <dd>
                  <Money amount={payoff.total_paid} currency={payoff.currency} locale={locale} />
                </dd>
              </div>
            </dl>
            <EvidenceLine evidence={payoff.evidence} locale={locale} />
          </div>
        }
      </Panel>
    </>}{edit&&
      <EditDialog locale={locale} title={current? t('Editar deuda','Edit debt'):t('Añadir deuda','Add debt')} fields={fields} path={current? `/credit/accounts/${current.id}`:'/credit/accounts'} method={current? 'PUT':'POST'} onClose={() => setEdit(null)} onSaved={changed} />
    }
  </div>
    ;
}
