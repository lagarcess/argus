import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Bookmark, Calculator, ChevronDown, RefreshCw } from 'lucide-react';
import type { PlacementInputs } from '../../contracts';
import type { PlatformPageProps } from '../../platform/types';
import { PageHeader, Panel, Field } from '../../platform/ui';
import { copy, errorText } from '../../i18n';
import { useMoneyView } from '../../useMoneyView';
import { Confirmation } from '../../components/Confirmation';
import { Comparison } from '../../components/Comparison';
import { Chat } from '../../components/Chat';
import { DemoControls, Notices, SavedDetail, SavedList } from '../../components/Saved';
import { ReceiptDrawer, type Receipt } from '../../components/ReceiptDrawer';
import './deposits.css';

export function DepositsPage({locale, query, revision, onNavigate, onChanged}: PlatformPageProps) {
  const view = useMoneyView(locale);
  const t = copy(locale);
  const es = locale !== 'en';
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [inputs, setInputs] = useState<PlacementInputs | null>(null);
  const [saved, setSaved] = useState(false);
  const openedTarget = useRef<string | null>(null);
  const home = view.home;
  const selected = query.get('decision');
  const noticeId = query.get('notice');
  const tab = query.get('tab') ?? (selected ? 'saved' : 'compare');
  useEffect(() => { void view.refresh(); }, [revision]);
  useEffect(() => {
    if (!inputs && home?.examples[0]) setInputs(home.examples[0].inputs);
  }, [home, inputs]);
  useEffect(() => {
    if (!selected) { openedTarget.current = null; return; }
    if (view.pending || !home) return;
    const target = `${selected}:${noticeId ?? ''}`;
    if (openedTarget.current === target) return;
    openedTarget.current = target;
    void view.openDecision(selected, home.notices.find(item => item.id === noticeId) ?? null);
  }, [selected, noticeId, home, view.pending]);
  const result = view.conversation.stage === 'result' ? view.conversation.result : null;
  const proposal = view.conversation.stage === 'confirmation' ? view.conversation.confirmation : null;
  const busy = view.pending !== null;
  async function prepare(event: FormEvent) {
    event.preventDefault();
    if (!inputs) return;
    setSaved(false);
    await view.prepare(inputs);
  }
  async function save() {
    await view.save();
    // The refreshed list is the durable success evidence, not a timer or animation.
    const refreshed = await view.refresh();
    if (result && refreshed?.saved.some(item => item.comparison_id === result.id)) {
      setSaved(true);
      onChanged();
    }
  }
  return <div className="p-deposits">
    <PageHeader eyebrow={es ? 'TU EFECTIVO' : 'YOUR CASH'} title={es ? 'Depósitos, con números claros.' : 'Deposits, with clear numbers.'} description={es ? 'Compara valores calculados al plazo que tú eliges. Cada cifra conserva su fuente.' : 'Compare modeled values over a horizon you choose. Every figure keeps its source.'} />
    <div className="p-tabs" aria-label={es ? 'Vista de depósitos' : 'Deposit view'}>
      <button className={tab === 'compare' ? 'active' : ''} onClick={() => onNavigate('deposits')}><Calculator size={16}/>{es ? 'Comparar' : 'Compare'}</button>
      <button className={tab === 'saved' ? 'active' : ''} onClick={() => onNavigate('deposits', {tab:'saved'})}><Bookmark size={16}/>{t.saved}{home && home.saved.length > 0 ? ` (${home.saved.length})` : ''}</button>
    </div>
    {!home ? <Panel><p role="status">{view.homeError ? errorText(view.homeError,t) : t.loading}</p>{view.homeError && <button className="p-button" onClick={() => {void view.refresh();}}><RefreshCw size={16}/>{t.retry}</button>}</Panel> : <>
      {tab === 'saved' ? selected && view.savedView?.decision.id === selected ? <SavedDetail key={`${selected}-${noticeId ?? ''}`} view={view.savedView} locale={locale} onBack={() => onNavigate('deposits',{tab:'saved'})} onReceipt={setReceipt}/> : <SavedList home={home} locale={locale} onOpen={id => onNavigate('deposits',{decision:id})} onReceipt={setReceipt} pending={busy}/> : <>
        {!proposal && !result && inputs && <Panel className="p-deposit-editor"><h2>{es ? '¿Cuánto tienes y cuándo lo necesitas?' : 'How much do you have, and when will you need it?'}</h2><form onSubmit={event => {void prepare(event);}}>
          <div className="p-form-grid">
            <Field label={t.amount}><input name="deposit_amount" type="number" inputMode="decimal" min="0.01" max="1000000000000" step="any" required value={inputs.amount} onChange={event => setInputs({...inputs,amount:event.target.value})}/></Field>
            <Field label={t.horizon}><input name="deposit_horizon" type="number" inputMode="numeric" min="1" max="3650" required value={inputs.horizon_days} onChange={event => setInputs({...inputs,horizon_days:Number(event.target.value)})}/></Field>
            <Field label={t.country}><select value={inputs.country} onChange={event => {const country = home.countries.find(item => item.code === event.target.value); if(country) setInputs({...inputs,country:country.code,currency:country.currencies[0]});}}>{home.countries.map(country => <option key={country.code} value={country.code}>{country.names[locale]}</option>)}</select></Field>
            <Field label={t.currency}><select value={inputs.currency} onChange={event => setInputs({...inputs,currency:event.target.value})}>{home.countries.find(country => country.code === inputs.country)?.currencies.map(currency => <option key={currency}>{currency}</option>)}</select></Field>
          </div>
          <Field label={t.currentInput} help={t.baselineHint}><input type="number" inputMode="decimal" step="any" value={inputs.current_annual_rate_pct ?? ''} onChange={event => setInputs({...inputs,current_annual_rate_pct:event.target.value || null})}/></Field>
          <p className="p-muted">{es ? 'Datos simulados. Revisarás el monto y el plazo antes del cálculo.' : 'Simulated data. Review the amount and horizon before calculating.'}</p>
          <button className="p-button p-primary" disabled={busy} type="submit">{busy ? t.working : es ? 'Revisar monto y plazo' : 'Review amount and horizon'}</button>
        </form></Panel>}
        {proposal && <Panel><Confirmation confirmation={proposal} countries={home.countries} locale={locale} pending={busy} onInputsChange={view.editConfirmation} onConfirm={() => {void view.compute();}}/></Panel>}
        {result && <><Comparison result={result} locale={locale} onReceipt={setReceipt}/><div className="p-actions p-deposit-result-actions"><button className="p-button p-primary" disabled={busy || saved} onClick={() => {void save();}}><Bookmark size={16}/>{saved ? (es ? 'Comparación guardada' : 'Comparison saved') : (es ? 'Guardar comparación' : 'Save comparison')}</button><button className="p-button" disabled={busy} onClick={() => {setInputs(result.inputs); view.restart(); setSaved(false);}}>{es ? 'Cambiar supuestos' : 'Change assumptions'}</button></div></>}
        <details className="p-deposit-question"><summary>{es ? 'También puedes plantearlo con palabras' : 'You can also describe it in words'}<ChevronDown size={16}/></summary><Chat home={home} locale={locale} conversation={view.conversation} draft={view.draft} pending={view.pending} error={view.error} onDraft={view.editDraft} onExample={view.chooseExample} onSend={() => {void view.send();}} onCompute={() => {void view.compute();}} onConfirmationEdit={view.editConfirmation} onSave={() => {void save();}}/></details>
      </>}
      {view.error && <p className="p-error" role="alert">{errorText(view.error,t)}</p>}
      {(view.loadingSources || home.source_status.state === 'stale') && <p className="p-callout" role="status">{view.loadingSources ? t.loadingSources : t.stale}</p>}
      <Notices notices={home.notices} saved={home.saved} onReceipt={setReceipt} locale={locale} onOpen={notice => {void view.openDecision(notice.decision_id,notice); onNavigate('deposits',{decision:notice.decision_id,notice:notice.id});}} pending={busy}/>
      {home.saved.length > 0 && <DemoControls locale={locale} loading={view.loadingSources || busy} onSimulate={scenario => {void view.simulate(scenario);}}/>}
    </>}
    <p className="p-deposit-disclosure">{t.disclosure}</p>
    {receipt && <ReceiptDrawer receipt={receipt} locale={locale} onClose={() => setReceipt(null)}/>}
  </div>;
}
