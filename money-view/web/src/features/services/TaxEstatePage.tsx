import { useEffect, useState,type FormEvent } from 'react';
import { z } from 'zod';
import { request } from '../../platform/client';
import { taxScenarioSchema as scenarioSchema, taxScenarioListSchema } from './tax-contracts';
import { useRecordFocus } from '../../argus/useRecordFocus';
import { useResource } from '../../platform/hooks';
import { PageHeader,Panel,Field,Money,EmptyState,EvidenceLine } from '../../platform/ui';
import { evidenceSchema,type PlatformPageProps } from '../../platform/types';
import { text,Recorded,dateLabel,today,currencies,Loading,EditDialog,DownloadLink,useAction,ErrorMessage,type InputSpec } from './shared';
const organizerSchema=z.object({ id: z.string(),country: z.string(),year: z.number(),currency: z.string(),status: z.string(),recorded_at: z.string() });
const taxSchema=z.object({ organizers: z.array(organizerSchema),items: z.array(z.object({ id: z.string(),organizer_id: z.string(),kind: z.string(),title: z.string(),amount: z.string().nullable(),effective_on: z.string(),completed: z.boolean(),recorded_at: z.string(),evidence: evidenceSchema.optional() })) });
const estateSchema=z.object({ assets: z.array(z.object({ id: z.string(),name: z.string(),currency: z.string(),value: z.string(),as_of: z.string(),recorded_at: z.string(),evidence: evidenceSchema.optional() })),contacts: z.array(z.object({ id: z.string(),name: z.string(),relationship: z.string(),email: z.string().nullable(),recorded_at: z.string() })),beneficiaries: z.array(z.object({ id: z.string(),asset_id: z.string(),shares: z.array(z.object({ contact_id: z.string(),share_pct: z.string() })),allocated_pct: z.string() })),documents: z.array(z.object({ id: z.string(),title: z.string(),location: z.string(),effective_on: z.string(),recorded_at: z.string() })),checklist: z.array(z.object({ id: z.string(),title: z.string(),completed: z.boolean(),recorded_at: z.string() })),legal_status: z.string() });
export function TaxEstatePage(props: PlatformPageProps) {
  const { locale }=props;
  const t=(es: string,en: string) => text(locale,es,en);
  const view = props.query.get('tab') === 'estate' ? 'estate' : 'tax';
  return <div className="p-stack services-page">
    <PageHeader eyebrow={t('DOCUMENTOS Y PATRIMONIO','DOCUMENTS & ESTATE')} title={t('Lo importante, en orden.','Keep what matters in order.')} description={t('Reúne tus cifras, contactos y documentos en un registro personal.','Bring figures, contacts and documents into a personal record.')} />
    <div className="p-tabs" aria-label={t('Área de organización','Organizer section')}>
      <button className={view==='tax'? 'active':''} aria-pressed={view==='tax'} onClick={() => props.onNavigate('tax-estate', {tab:'tax'})}>
        {t('Organizador fiscal','Tax organizer')}
      </button>
      <button className={view==='estate'? 'active':''} aria-pressed={view==='estate'} onClick={() => props.onNavigate('tax-estate', {tab:'estate'})}>
        {t('Inventario patrimonial','Estate inventory')}
      </button>
    </div>
    {view==='tax'?
      <TaxOrganizer {...props} />
      :
      <EstateInventory {...props} />
    }
  </div>
    ;
}
function TaxOrganizer({ locale,revision,onChanged,currency,query,onNavigate }: PlatformPageProps) {
  const t=(es: string,en: string) => text(locale,es,en);
  const resource=useResource(() => request('/tax',taxSchema),[revision]);
  const [selected,setSelected]=useState('');
  const [dialog,setDialog]=useState<'organizer'|'income'|'expense'|'document'|'checklist'|null>(null);
  const [rate,setRate]=useState('');
  const [result,setResult]=useState<z.infer<typeof scenarioSchema>|null>(null);
  const [error,setError]=useState<unknown>(null);
  const [pending,setPending]=useState(false);
  const d=resource.data;
  const targetId=query.get('record_id');
  const targetOrganizerId=d?.organizers.find(item => item.id===targetId)?.id ?? d?.items.find(item => item.id===targetId)?.organizer_id;
  const scenarioTarget=d && targetId && !targetOrganizerId ? targetId : null;
  const savedScenario=useResource(() => scenarioTarget ? request(`/tax/scenarios/${encodeURIComponent(scenarioTarget)}`,scenarioSchema) : Promise.resolve(null),[scenarioTarget,revision]);
  useEffect(() => {
    setResult(savedScenario.data);
    if(savedScenario.data) { setSelected(savedScenario.data.organizer_id); setRate(savedScenario.data.user_rate_pct); }
  },[savedScenario.data]);
  useEffect(() => { if(targetOrganizerId) setSelected(targetOrganizerId); },[targetOrganizerId]);
  const organizer=d?.organizers.find(o => o.id===(selected||d.organizers[0]?.id));
  const items=d?.items.filter(i => i.organizer_id===organizer?.id)||[];
  const recordRef=useRecordFocus(targetId,[d,organizer?.id,result?.id]);
  const [historyOffset,setHistoryOffset]=useState(0);
  useEffect(() => { setHistoryOffset(0); },[organizer?.id]);
  const history=useResource(() => organizer ? request(`/tax/scenarios?organizer_id=${encodeURIComponent(organizer.id)}&limit=20&offset=${historyOffset}`,taxScenarioListSchema) : Promise.resolve(null),[organizer?.id,historyOffset,revision]);
  const changed=() => { resource.reload(); onChanged(); setResult(null); };
  const action=useAction(locale,changed);
  async function calculate(e: FormEvent) {
    e.preventDefault(); if(!organizer)
      return; setError(null); setPending(true); setResult(null); try {
        const saved=await request('/tax/scenario',scenarioSchema,{ method: 'POST',body: JSON.stringify({ organizer_id: organizer.id,user_rate_pct: rate }) });
        setResult(saved); onChanged();
        onNavigate('tax-estate',{tab:'tax',record_id:saved.id});
      }
    catch(e) {
      setError(e);
    }
    finally {
      setPending(false);
    }
  }
  const kindName=(kind: string) => ({ income: t('Ingreso','Income'),expense: t('Gasto','Expense'),document: t('Documento','Document'),checklist: t('Pendiente','Checklist item') })[kind]||kind;
  const fields: InputSpec[]=dialog==='organizer'? [{ name: 'country',es: 'País (código de dos letras)',en: 'Country (two-letter code)',value: 'DO',help: t('Solo identifica tu carpeta. No aplica reglas fiscales de ese país.','Identifies your folder only. It does not apply that country’s tax rules.') },{ name: 'year',es: 'Año',en: 'Year',type: 'number',min: '1900',max: '2100',step: '1',value: String(new Date().getFullYear()) },{ name: 'currency',es: 'Moneda',en: 'Currency',options: currencies,value: currency }]:[{ name: 'title',es: 'Descripción',en: 'Description' },...((dialog==='income'||dialog==='expense')? [{ name: 'amount',es: 'Importe',en: 'Amount',type: 'number',min: '0',step: 'any' }]:[]),{ name: 'effective_on',es: 'Fecha del registro',en: 'Effective date',type: 'date',value: organizer? `${organizer.year}-${today().slice(5)}`:today() }];
  return <div className="p-stack services-record-surface" ref={recordRef}>
    <Loading locale={locale} {...resource} retry={resource.reload} />
    <Loading locale={locale} {...savedScenario} retry={savedScenario.reload} />
    <Panel data-record-id={organizer?.id} tabIndex={-1}>
      <div className="p-toolbar">
        <div>
          <h2>
            {t('Tu carpeta fiscal','Your tax folder')}
          </h2>
          <p className="p-muted">
            {t('Hoja personal de trabajo. No calcula obligaciones fiscales ni presenta declaraciones.','A personal worksheet. It does not calculate tax obligations or file returns.')}
          </p>
        </div>
        <button className="p-button" onClick={() => setDialog('organizer')}>
          {t('Crear carpeta','Create folder')}
        </button>
      </div>
      {d&&<>{d.organizers.length>0?
        <Field label={t('País, año y moneda','Country, year and currency')}>
          <select value={organizer?.id||''} onChange={e => { setSelected(e.target.value); setResult(null); onNavigate('tax-estate',{tab:'tax',record_id:e.target.value}); }}>
            {d.organizers.map(o =>
              <option value={o.id} key={o.id}>
                {o.country} · {o.year} · {o.currency}
              </option>
            )}
          </select>
        </Field>
        :
        <EmptyState title={t('Empieza por el país y el año','Start with a country and year')} description={t('Después podrás añadir ingresos, gastos y documentos.','Then add income, expenses and documents.')} />
      }</>}
    </Panel>
    {organizer&&<>
      <Panel>
        <div className="p-toolbar">
          <div>
            <h2>
              {t('Registros y revisión','Records and review')}
            </h2>
            <span className="p-badge">
              {organizer.status==='complete'? t('Carpeta completa','Folder complete'):t('En preparación','In progress')}
            </span>
          </div>
          <button className="p-button-secondary" disabled={action.pending} onClick={() => void action.run(`/tax/organizers/${organizer.id}`,'PATCH',{ status: organizer.status==='complete'? 'open':'complete' })}>
            {organizer.status==='complete'? t('Reabrir carpeta','Reopen folder'):t('Marcar carpeta completa','Mark folder complete')}
          </button>
        </div>
        <Recorded locale={locale} at={organizer.recorded_at} />
        {action.feedback}
        <div className="p-actions">
          {(['income','expense','document','checklist'] as const).map(kind =>
            <button key={kind} className="p-button-secondary" disabled={organizer.status==='complete'} onClick={() => setDialog(kind)}>
              {t('Añadir','Add')} {kindName(kind).toLocaleLowerCase()}
            </button>
          )}
        </div>
        <div className="p-ledger">
          {items.map(i =>
            <article className="services-tax-row" key={i.id} data-record-id={i.id} tabIndex={-1}>
              <label className="services-check">
                <input type="checkbox" checked={i.completed} disabled={action.pending||organizer.status==='complete'} onChange={e => void action.run(`/tax/items/${i.id}`,'PATCH',{ completed: e.target.checked })} />
                <span>
                  <strong>
                    {i.title}
                  </strong>
                  <small>
                    {kindName(i.kind)} · {dateLabel(i.effective_on,locale)}
                  </small>
                </span>
              </label>
              {i.amount!==null&&
                <Money amount={i.amount} currency={organizer.currency} locale={locale} />
              }<>{i.evidence?
                <EvidenceLine evidence={i.evidence} locale={locale} />
                :
                <Recorded locale={locale} at={i.recorded_at} />
              }</>
            </article>
          )}
        </div>
        {items.length===0&&
          <EmptyState title={t('Esta carpeta está vacía','This folder is empty')} />
        }
        <div className="p-actions">
          <DownloadLink path={`/tax/organizers/${organizer.id}/export?format=csv`}>
            {t('Descargar hoja CSV','Download CSV worksheet')}
          </DownloadLink>
          <DownloadLink path={`/tax/organizers/${organizer.id}/export?format=json`}>
            {t('Descargar registros JSON','Download JSON records')}
          </DownloadLink>
        </div>
      </Panel>
      <Panel>
        <h2>
          {t('Calcula con tu propia tasa','Calculate with your own rate')}
        </h2>
        <p>
          {t('Este ejercicio multiplica tus ingresos menos gastos por una tasa que tú indicas. No incorpora normas, deducciones ni tramos fiscales.','This exercise multiplies your recorded income minus expenses by a rate you enter. It does not include tax rules, deductions or tax brackets.')}
        </p>
        <Loading locale={locale} {...history} retry={history.reload} />
        {history.data && history.data.count>0 && <div className="p-stack">
          <Field label={t('Hojas guardadas','Saved worksheets')}>
            <select value={history.data.items.some(item => item.id===targetId)? targetId||'':''} onChange={e => { if(e.target.value) onNavigate('tax-estate',{tab:'tax',record_id:e.target.value}); }}>
              <option value="">{t('Selecciona una hoja guardada','Choose a saved worksheet')}</option>
              {history.data.items.map(item => <option key={item.id} value={item.id}>{dateLabel(item.recorded_at,locale)} · {item.user_rate_pct}%</option>)}
            </select>
          </Field>
          <div className="p-actions">
            <span>{t('Guardadas','Saved')}: {history.data.count}</span>
            <button className="p-button-secondary" disabled={historyOffset===0} onClick={() => setHistoryOffset(value => Math.max(0,value-20))}>{t('Anterior','Previous')}</button>
            <button className="p-button-secondary" disabled={historyOffset+history.data.items.length>=history.data.count} onClick={() => setHistoryOffset(value => value+20)}>{t('Siguiente','Next')}</button>
          </div>
        </div>}
        <form className="p-form-grid" onSubmit={calculate}>
          <Field label={t('Tasa del escenario (%)','Scenario rate (%)')}>
            <input type="number" min="0" max="100" step="any" required value={rate} onChange={e => { setRate(e.target.value); setResult(null); }} />
          </Field>
          <button className="p-button" disabled={pending}>
            {pending? t('Calculando…','Calculating…'):t('Calcular hoja de trabajo','Calculate worksheet')}
          </button>
        </form>
        <ErrorMessage locale={locale} error={error} />
        {result&&
          <div className="services-result" role="status" data-record-id={result.id} tabIndex={-1}>
            <dl className="services-facts">
              <div>
                <dt>
                  {t('Ingresos registrados','Recorded income')}
                </dt>
                <dd>
                  <Money amount={result.income} currency={result.currency} locale={locale} />
                  <EvidenceLine evidence={result.evidence} locale={locale} />
                </dd>
              </div>
              <div>
                <dt>
                  {t('Gastos registrados','Recorded expenses')}
                </dt>
                <dd>
                  <Money amount={result.expenses} currency={result.currency} locale={locale} />
                  <EvidenceLine evidence={result.evidence} locale={locale} />
                </dd>
              </div>
              <div>
                <dt>
                  {t('Resultado a tu tasa','Result at your rate')} ({result.user_rate_pct}%)
                </dt>
                <dd>
                  <Money amount={result.scenario_amount} currency={result.currency} locale={locale} />
                  <EvidenceLine evidence={result.evidence} locale={locale} />
                </dd>
              </div>
            </dl>
            <EvidenceLine evidence={result.rate_evidence} locale={locale} />
            <p className="p-muted">
              {t('Hoja guardada con los registros de ese momento','Saved worksheet using records from that moment')} · {dateLabel(result.recorded_at,locale)} · {t('Solo hoja de trabajo','Worksheet only')}
            </p>
          </div>
        }
      </Panel>
    </>}{dialog&&
      <EditDialog key={dialog} locale={locale} title={dialog==='organizer'? t('Crear carpeta fiscal','Create tax folder'):`${t('Añadir','Add')} ${kindName(dialog).toLowerCase()}`} path={dialog==='organizer'? '/tax/organizers':'/tax/items'} fields={fields} extra={dialog==='organizer'? {}:{ organizer_id: organizer?.id,kind: dialog }} transform={values => dialog==='organizer'? { ...values,country: values.country.toUpperCase(),year: Number(values.year) }:values} onClose={() => setDialog(null)} onSaved={changed} />
    }</div>;
}
function EstateInventory({ locale,revision,onChanged,currency,query }: PlatformPageProps) {
  const t=(es: string,en: string) => text(locale,es,en);
  const resource=useResource(() => request('/estate',estateSchema),[revision]);
  const [dialog,setDialog]=useState<'asset'|'contact'|'document'|'checklist'|null>(null);
  const [allocate,setAllocate]=useState<string|null>(null);
  const d=resource.data;
  const targetId=query.get('record_id');
  const recordRef=useRecordFocus(targetId,[d]);
  const changed=() => { resource.reload(); onChanged(); };
  const action=useAction(locale,changed);
  const fields: Record<string,InputSpec[]>={ asset: [{ name: 'name',es: 'Nombre del activo',en: 'Asset name' },{ name: 'currency',es: 'Moneda',en: 'Currency',options: currencies,value: currency },{ name: 'value',es: 'Valor registrado',en: 'Recorded value',type: 'number',min: '0',step: 'any' },{ name: 'as_of',es: 'Fecha del valor',en: 'Value as of',type: 'date',value: today() }],contact: [{ name: 'name',es: 'Nombre',en: 'Name' },{ name: 'relationship',es: 'Relación',en: 'Relationship' },{ name: 'email',es: 'Correo (opcional)',en: 'Email (optional)',type: 'email',required: false }],document: [{ name: 'title',es: 'Documento',en: 'Document' },{ name: 'location',es: 'Dónde encontrarlo',en: 'Where to find it',help: t('Guarda una referencia. No subas archivos ni contraseñas.','Save a reference. Do not upload files or passwords.') },{ name: 'effective_on',es: 'Fecha del documento',en: 'Document date',type: 'date',value: today() }],checklist: [{ name: 'title',es: 'Tarea de revisión',en: 'Review task' }] };
  const titles={ asset: t('Añadir activo','Add asset'),contact: t('Añadir contacto','Add contact'),document: t('Guardar ubicación','Save location'),checklist: t('Añadir tarea','Add task') };
  const paths={ asset: '/estate/assets',contact: '/estate/contacts',document: '/estate/documents',checklist: '/estate/checklist' };
  return <div className="p-stack services-record-surface" ref={recordRef}>
    <Loading locale={locale} {...resource} retry={resource.reload} />
    <Panel>
      <div className="p-toolbar">
        <div>
          <h2>
            {t('Tu inventario personal','Your personal inventory')}
          </h2>
          <p className="p-muted">
            {t('Solo organización. No es un testamento, una designación legal ni una transferencia de activos.','Organization only. This is not a will, legal designation or asset transfer.')}
          </p>
        </div>
        <button className="p-button" onClick={() => setDialog('asset')}>
          {t('Añadir activo','Add asset')}
        </button>
      </div>
      <div className="p-actions">
        <DownloadLink path="/estate/export?format=csv">
          {t('Descargar inventario CSV','Download inventory CSV')}
        </DownloadLink>
        <DownloadLink path="/estate/export?format=json">
          {t('Descargar inventario JSON','Download inventory JSON')}
        </DownloadLink>
      </div>
    </Panel>
    {d&&<>
      <Panel>
        <h2>
          {t('Activos y distribución de referencia','Assets and reference allocation')}
        </h2>
        {!d.assets.length&&
          <EmptyState title={t('Aún no hay activos registrados','No assets recorded yet')} />
        } {d.assets.map(a => {
          const allocation=d.beneficiaries.find(b => b.asset_id===a.id); return <article className="services-account" key={a.id} data-record-id={a.id} tabIndex={-1}>
            <div className="p-toolbar">
              <h3>
                {a.name}
              </h3>
              <Money amount={a.value} currency={a.currency} locale={locale} />
            </div>
            {a.evidence?
              <EvidenceLine evidence={a.evidence} locale={locale} />
              :<>
                <p className="p-muted">
                  {t('Valor aportado por ti','Value entered by you')} · {dateLabel(a.as_of,locale)}
                </p>
                <Recorded locale={locale} at={a.recorded_at} />
              </>}
            <div className="services-allocation">
              {allocation?.shares.map(s =>
                <div key={s.contact_id}>
                  <span>
                    {d.contacts.find(c => c.id===s.contact_id)?.name||t('Contacto','Contact')}
                  </span>
                  <strong>
                    {s.share_pct}%
                  </strong>
                </div>
              )}
            </div>
            <div className="p-toolbar">
              <p className="p-muted">
                {allocation? `${t('Distribución registrada','Recorded allocation')}: ${allocation.allocated_pct}%`:t('Sin distribución de referencia','No reference allocation')}
              </p>
              <button className="p-button-secondary" disabled={!d.contacts.length} onClick={() => setAllocate(a.id)}>
                {t('Editar distribución','Edit allocation')}
              </button>
            </div>
            {!d.contacts.length&&
              <p className="p-muted">
                {t('Añade un contacto para registrar porcentajes.','Add a contact to record percentages.')}
              </p>
            }
          </article>
            ;
        })}
      </Panel>
      <div className="services-columns">
        <Panel>
          <div className="p-toolbar">
            <h2>
              {t('Personas de referencia','Reference contacts')}
            </h2>
            <button className="p-button-secondary" onClick={() => setDialog('contact')}>
              {t('Añadir contacto','Add contact')}
            </button>
          </div>
          {d.contacts.map(c =>
            <article className="services-detail-row" key={c.id} data-record-id={c.id} tabIndex={-1}>
              <strong>
                {c.name}
              </strong>
              <span>
                {c.relationship}
              </span>
              {c.email&&
                <span className="p-muted">
                  {c.email}
                </span>
              }
              <Recorded locale={locale} at={c.recorded_at} />
            </article>
          )}{!d.contacts.length&&
            <EmptyState title={t('¿A quién incluirías?','Who would you include?')} description={t('Los contactos no reciben mensajes.','Contacts do not receive messages.')} />
          }
        </Panel>
        <Panel>
          <div className="p-toolbar">
            <h2>
              {t('Dónde están los documentos','Where documents are kept')}
            </h2>
            <button className="p-button-secondary" onClick={() => setDialog('document')}>
              {t('Añadir ubicación','Add location')}
            </button>
          </div>
          {d.documents.map(doc =>
            <article className="services-detail-row" key={doc.id} data-record-id={doc.id} tabIndex={-1}>
              <strong>
                {doc.title}
              </strong>
              <span>
                {doc.location}
              </span>
              <p className="p-muted">
                {t('Documento del','Document dated')} {dateLabel(doc.effective_on,locale)}
              </p>
              <Recorded locale={locale} at={doc.recorded_at} />
            </article>
          )}{!d.documents.length&&
            <EmptyState title={t('Guarda una referencia útil','Save a useful reference')} description={t('Por ejemplo, el nombre de una carpeta o un archivador.','For example, the name of a folder or filing cabinet.')} />
          }
        </Panel>
      </div>
      <Panel>
        <div className="p-toolbar">
          <h2>
            {t('Lista de revisión personal','Personal review checklist')}
          </h2>
          <button className="p-button-secondary" onClick={() => setDialog('checklist')}>
            {t('Añadir tarea','Add task')}
          </button>
        </div>
        {action.feedback}{d.checklist.map(item =>
          <div className="services-tax-row" key={item.id} data-record-id={item.id} tabIndex={-1}>
            <label className="services-check">
              <input type="checkbox" checked={item.completed} disabled={action.pending} onChange={e => void action.run(`/estate/checklist/${item.id}`,'PATCH',{ completed: e.target.checked })} />
              <span>
                {item.title}
              </span>
            </label>
            <Recorded locale={locale} at={item.recorded_at} />
          </div>
        )}{!d.checklist.length&&
          <EmptyState title={t('Tu próxima revisión empieza aquí','Your next review starts here')} />
        }
      </Panel>
    </>}{dialog&&
      <EditDialog key={dialog} locale={locale} title={titles[dialog]} path={paths[dialog]} fields={fields[dialog]} transform={v => dialog==='contact'? { ...v,email: v.email||null }:v} onClose={() => setDialog(null)} onSaved={changed} />
    } {allocate&&d&&
      <EditDialog locale={locale} title={t('Distribución de referencia','Reference allocation')} path={`/estate/assets/${allocate}/beneficiaries`} method="PUT" fields={d.contacts.map(c => ({ name: c.id,es: `${c.name} (%)`,en: `${c.name} (%)`,type: 'number',min: '0',max: '100',step: 'any',value: d.beneficiaries.find(b => b.asset_id===allocate)?.shares.find(s => s.contact_id===c.id)?.share_pct||'0',help: t('El total no puede superar 100%. Cero excluye al contacto. Sin validez legal.','Total must not exceed 100%. Zero excludes a contact. No legal validity.') }))} transform={v => ({ shares: Object.entries(v).filter(([,pct]) => Number(pct)>0).map(([contact_id,share_pct]) => ({ contact_id,share_pct })) })} onClose={() => setAllocate(null)} onSaved={changed} />
    }</div>;
}
