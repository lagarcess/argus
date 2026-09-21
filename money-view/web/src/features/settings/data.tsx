import { useEffect, useState } from 'react';
import { z } from 'zod';
import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import { EmptyState, Field } from '../../platform/ui';
import { dateText, downloadJson, jsonObjectSchema, usageSchema, type Settings, type Text } from './contracts';
import { ActionState, LoadState, useMutation, write } from './shared';

function domainTitle(domain: string, t: Text) {
  const labels: Record<string, string> = { ledger: t('Cuentas y movimientos', 'Accounts and transactions'), planning: t('Planes y escenarios', 'Plans and scenarios'), investing: t('Inversiones simuladas', 'Simulated investments'), investments: t('Inversiones simuladas', 'Simulated investments'), services: t('Servicios demo', 'Demo services'), assistant: t('Conversaciones', 'Conversations') };
  return labels[domain] ?? domain;
}

export function DataControls({ settings, t, onChanged }: { settings: Settings; t: Text; onChanged: () => void }) {
  const mutation = useMutation(t, onChanged);
  const [action, setAction] = useState<'reset' | 'account' | 'conversations' | null>(null);
  const [confirmation, setConfirmation] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const expected = action === 'reset' ? 'RESET THIS HOUSEHOLD' : action === 'conversations' ? 'TRASH HOUSEHOLD CONVERSATIONS' : 'DELETE MY LOCAL ACCOUNT';
  return <div className="p-stack"><p>{t('Los datos de esta demo se guardan en el servidor local de Clara. La exportación contiene solo este hogar y excluye contraseñas y tokens de sesión.', 'This demo stores data on Clara’s local server. The export includes only this household and excludes passwords and session tokens.')}</p>
    <button className="p-button-secondary" disabled={mutation.busy} onClick={() => void mutation.run(async () => downloadJson(await request('/settings/data/export', jsonObjectSchema), 'clara-household.json'))}>{t('Exportar datos del hogar (JSON)', 'Export household data (JSON)')}</button>
    <p className="p-muted">{t('Áreas incluidas', 'Included areas')}: {settings.capabilities.data_domains.map(domain => domainTitle(domain, t)).join(', ') || t('Identidad y preferencias', 'Identity and preferences')}</p>
    {settings.capabilities.archive_conversations === true && <><h3>{t('Historial de conversaciones', 'Conversation history')}</h3><button className="p-button-secondary" disabled={settings.household.role !== 'owner' || mutation.busy} onClick={() => { setAction('conversations'); setConfirmation(''); setName(''); }}>{t('Mover todo el historial a la papelera', 'Move all history to recently deleted')}</button></>}
    <h3>{t('Acciones definitivas', 'Permanent actions')}</h3>
    <div className="p-actions"><button className="p-button-danger" disabled={settings.household.role !== 'owner' || mutation.busy} onClick={() => { setAction('reset'); setConfirmation(''); setName(''); }}>{t('Restablecer datos del hogar', 'Reset household data')}</button><button className="p-button-danger" disabled={mutation.busy} onClick={() => { setAction('account'); setConfirmation(''); setName(''); }}>{t('Eliminar mi cuenta local', 'Delete my local account')}</button></div>
    {settings.household.role !== 'owner' && <p className="p-muted">{t('Solo una persona propietaria puede restablecer el hogar.', 'Only an owner can reset the household.')}</p>}
    {action && <form className="settings-confirm p-stack" onSubmit={event => { event.preventDefault(); void mutation.run(() => action === 'reset' ? write('/settings/data/reset', 'POST', { confirmation }) : action === 'conversations' ? write('/assistant/conversations/trash-all', 'POST', { confirmation }) : write('/settings/account', 'DELETE', { confirmation, current_password: password }), () => { if (action === 'account') window.dispatchEvent(new Event('clara:session-expired')); setAction(null); }); }}>
      <h3>{action !== 'account' ? settings.household.name : settings.profile.display_name}</h3>
      <p>{action === 'conversations' ? t('Todas las conversaciones activas y archivadas de este hogar irán a Eliminados recientemente. Incluye el historial de las demás personas del hogar. Podrás restaurarlas desde allí.', 'All active and archived conversations in this household will move to Recently deleted. This includes other household members’ history. You can restore them there.') : action === 'reset' ? t('Se vaciarán los registros financieros, conversaciones, recuerdos y comentarios de este hogar. Se restablecerán sus preferencias. Las personas y sus contraseñas se conservan. No se vuelven a crear los datos de ejemplo.', 'Financial records, conversations, memories and feedback in this household will be emptied. Preferences will reset. Members and passwords remain. Example data is not recreated.') : t('Se eliminarán tu acceso y tus datos personales. Si compartes el hogar, sus datos se conservan. Si eres su única persona, también se eliminan sus datos. La última persona propietaria de un hogar compartido debe transferir su rol primero.', 'Your access and personal data will be deleted. Shared household data remains. If you are its only member, its data is also deleted. The last owner of a shared household must transfer ownership first.')}</p>
      <Field label={t('Confirma el nombre', 'Confirm the name')} help={action !== 'account' ? settings.household.name : settings.profile.display_name}><input required value={name} onChange={event => setName(event.target.value)}/></Field>
      <Field label={t(`Escribe ${expected} para confirmar`, `Type ${expected} to confirm`)}><input required value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="off"/></Field>
      {action === 'account' && <Field label={t('Contraseña actual', 'Current password')}><input required type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)}/></Field>}
      <div className="p-actions"><button type="button" autoFocus className="p-button-secondary" disabled={mutation.busy} onClick={() => setAction(null)}>{t('Cancelar', 'Cancel')}</button><button type="submit" className="p-button-danger" disabled={mutation.busy || confirmation !== expected || name !== (action !== 'account' ? settings.household.name : settings.profile.display_name)}>{mutation.busy ? t('Procesando…', 'Working…') : action === 'conversations' ? t('Mover todo a la papelera', 'Move all to recently deleted') : action === 'reset' ? t('Vaciar este hogar', 'Empty this household') : t('Eliminar mi cuenta', 'Delete my account')}</button></div>
    </form>}<ActionState {...mutation}/>
  </div>;
}

export function Usage({ t, locale }: { t: Text; locale: string }) {
  const resource = useResource(() => request('/settings/usage', usageSchema), []);
  const metricNames: Record<string, string> = { active_sessions: t('Sesiones activas', 'Active sessions'), confirmed_memories: t('Recuerdos confirmados', 'Confirmed memories'), local_feedback: t('Comentarios guardados', 'Saved feedback'), accounts: t('Cuentas', 'Accounts'), transactions: t('Movimientos', 'Transactions'), goals: t('Metas', 'Goals'), budgets: t('Presupuestos', 'Budgets'), scenarios: t('Escenarios', 'Scenarios'), conversations: t('Conversaciones', 'Conversations'), messages: t('Mensajes', 'Messages'), holdings: t('Posiciones', 'Holdings') };
  Object.assign(metricNames, { planning_records: t('Planes guardados', 'Saved plans'), service_records: t('Registros de servicios', 'Service records'), answers: t('Respuestas guardadas', 'Saved answers'), simulation_books: t('Cuentas de simulación', 'Simulation accounts'), confirmed_orders: t('Órdenes simuladas confirmadas', 'Confirmed simulated orders'), recurring_plans: t('Planes recurrentes', 'Recurring plans') });
  return <div className="p-stack"><p className="p-muted">{t('Recuento de registros guardados. No son cuotas ni cargos.', 'Counts of saved records. These are not quotas or charges.')}</p><LoadState {...resource} retry={resource.reload} t={t}/>{resource.data && <><p className="p-muted">{t('Consultado', 'Checked')}: {dateText(resource.data.as_of, locale)}</p>{Object.entries({ [t('Tu perfil', 'Your profile')]: resource.data.metrics, ...resource.data.domains }).map(([domain, metrics]) => <section key={domain}><h3>{domainTitle(domain, t)}</h3><dl className="settings-counts">{Object.entries(metrics).map(([key, count]) => <div key={key}><dt>{metricNames[key] ?? key.replaceAll('_', ' ')}</dt><dd>{new Intl.NumberFormat(locale).format(count)}</dd></div>)}</dl></section>)}</>}</div>;
}

const conversationListSchema = z.object({
  items: z.array(z.object({ id: z.string(), title: z.string(), updated_at: z.string().optional() }).passthrough()),
  total: z.number().int().nonnegative(),
  limit: z.number().int().min(1).max(100),
  offset: z.number().int().nonnegative(),
});
const historyPageSize = 20;
export function ConversationRecovery({ state, t, locale, onChanged }: { state: 'archived' | 'trashed'; t: Text; locale: string; onChanged: () => void }) {
  const [offset, setOffset] = useState(0);
  const resource = useResource(() => request(`/assistant/conversations?state=${state}&limit=${historyPageSize}&offset=${offset}`, conversationListSchema), [state, offset]);
  const mutation = useMutation(t, () => { resource.reload(); onChanged(); });
  const page = resource.data;
  useEffect(() => {
    if (!resource.loading && page && offset > 0 && offset >= page.total) {
      setOffset(Math.max(0, Math.ceil(page.total / page.limit) - 1) * page.limit);
    }
  }, [page, offset, resource.loading]);
  const number = (value: number) => new Intl.NumberFormat(locale).format(value);
  return <div className="p-stack">
    <p className="p-muted">{t('Restaurar devuelve la conversación a tu lista activa.', 'Restoring returns the conversation to your active list.')}</p>
    <LoadState {...resource} retry={resource.reload} t={t}/>
    {page?.total === 0 && !resource.loading && <EmptyState title={state === 'archived' ? t('No hay conversaciones archivadas', 'No archived conversations') : t('La papelera está vacía', 'Recently deleted is empty')}/>}
    {page && page.total > 0 && page.items.length > 0 && <p className="p-muted" role="status">{number(page.offset + 1)}–{number(page.offset + page.items.length)} {t('de', 'of')} {number(page.total)} {t('conversaciones', 'conversations')}</p>}
    {page?.items.map(item => <article key={item.id} className="settings-session">
      <div><strong>{item.title}</strong>{item.updated_at && <p className="p-muted">{dateText(item.updated_at, locale)}</p>}</div>
      <button className="p-button-secondary" disabled={mutation.busy || resource.loading} onClick={() => void mutation.run(() => write(`/assistant/conversations/${encodeURIComponent(item.id)}`, 'PATCH', { state: 'active' }), () => {
        if (page.items.length === 1 && page.offset > 0) setOffset(Math.max(0, page.offset - page.limit));
      })}>{t('Restaurar', 'Restore')}</button>
    </article>)}
    {page && page.total > 0 && <nav className="p-pagination" aria-label={t('Páginas del historial', 'History pages')}>
      <button className="p-button-secondary" disabled={mutation.busy || resource.loading || page.offset === 0} onClick={() => setOffset(Math.max(0, page.offset - page.limit))}>{t('Anterior', 'Previous')}</button>
      <span>{t('Página', 'Page')} {number(Math.floor(page.offset / page.limit) + 1)} {t('de', 'of')} {number(Math.max(1, Math.ceil(page.total / page.limit)))}</span>
      <button className="p-button-secondary" disabled={mutation.busy || resource.loading || page.offset + page.limit >= page.total} onClick={() => setOffset(page.offset + page.limit)}>{t('Siguiente', 'Next')}</button>
    </nav>}
    <ActionState {...mutation}/>
  </div>;
}
