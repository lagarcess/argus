import { useState } from 'react';
import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import { EmptyState, Field } from '../../platform/ui';
import { dateText, downloadJson, memoriesSchema, type Text } from './contracts';
import { ActionState, LoadState, SaveButton, useMutation, write } from './shared';

export function Memories({ t, locale, onChanged }: { t: Text; locale: string; onChanged: () => void }) {
  const resource = useResource(() => request('/settings/memories', memoriesSchema), []);
  const mutation = useMutation(t, () => { resource.reload(); onChanged(); });
  const [editing, setEditing] = useState<string | null>(null);
  const [content, setContent] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [resetConfirmation, setResetConfirmation] = useState('');
  return <div className="p-stack">
    <p className="p-muted">{t('Solo se guardan hechos que tú confirmas. Pertenecen a tu perfil dentro de este hogar. Desactivarlos conserva los registros y deja de usarlos en Argus.', 'Only facts you confirm are saved. They belong to your profile within this household. Turning them off keeps the records and stops their use in Argus.')}</p>
    <LoadState {...resource} retry={resource.reload} t={t}/>
    {resource.data && <>
      <label className="settings-check"><input type="checkbox" checked={resource.data.enabled} disabled={mutation.busy} onChange={event => void mutation.run(() => write('/settings/memories', 'PATCH', { enabled: event.target.checked }))}/>{t('Usar mis recuerdos confirmados', 'Use my confirmed memories')}</label>
      <div className="p-actions"><button className="p-button" onClick={() => { setEditing('new'); setContent(''); setConfirmed(false); }}>{t('Agregar recuerdo', 'Add memory')}</button><button className="p-button-secondary" disabled={mutation.busy} onClick={() => void mutation.run(async () => downloadJson(await request('/settings/memories/export', memoriesSchema), 'argus-memories.json'))}>{t('Exportar JSON', 'Export JSON')}</button></div>
      {resource.data.items.length === 0 && <EmptyState title={t('Sin recuerdos confirmados', 'No confirmed memories')} description={t('Agrega un dato que quieras conservar para tus conversaciones.', 'Add a fact you want to keep for your conversations.')}/>}
      {resource.data.items.map(memory => <article className="settings-memory" key={memory.id}><p>{memory.content}</p><small className="p-muted">{t('Actualizado', 'Updated')}: {dateText(memory.updated_at, locale)}</small><div className="p-actions"><button className="p-button-ghost" onClick={() => { setEditing(memory.id); setContent(memory.content); setConfirmed(false); }}>{t('Editar', 'Edit')}</button><button className="p-button-ghost" onClick={() => setRemoving(memory.id)}>{t('Eliminar', 'Delete')}</button></div></article>)}
      {resource.data.items.length > 0 && <button className="p-button-danger" onClick={() => { setRemoving('all'); setResetConfirmation(''); }}>{t('Eliminar mis recuerdos', 'Delete my memories')}</button>}
    </>}
    {editing && <form className="settings-confirm p-stack" onSubmit={event => { event.preventDefault(); void mutation.run(() => write(editing === 'new' ? '/settings/memories' : `/settings/memories/${encodeURIComponent(editing)}`, editing === 'new' ? 'POST' : 'PATCH', { content: content.trim(), confirmed }), () => setEditing(null)); }}><Field label={t('Recuerdo', 'Memory')}><textarea required minLength={1} maxLength={2000} rows={4} value={content} onChange={event => setContent(event.target.value)}/></Field><label className="settings-check"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)}/>{t('Confirmo que este dato es correcto y quiero guardarlo.', 'I confirm this fact is correct and want to save it.')}</label><div className="p-actions"><button type="button" className="p-button-secondary" disabled={mutation.busy} onClick={() => setEditing(null)}>{t('Cancelar', 'Cancel')}</button><SaveButton busy={mutation.busy} t={t}/></div></form>}
    {removing && <section className="settings-confirm p-stack"><p>{removing === 'all' ? t('Se eliminarán todos tus recuerdos de este hogar. Esta acción no se puede deshacer.', 'All your memories in this household will be deleted. This cannot be undone.') : t('Este recuerdo se eliminará definitivamente.', 'This memory will be permanently deleted.')}</p>{removing !== 'all' && <blockquote>{resource.data?.items.find(item => item.id === removing)?.content}</blockquote>}{removing === 'all' && <Field label={t('Escribe DELETE MY MEMORIES para confirmar', 'Type DELETE MY MEMORIES to confirm')}><input value={resetConfirmation} onChange={event => setResetConfirmation(event.target.value)}/></Field>}<div className="p-actions"><button autoFocus className="p-button-secondary" disabled={mutation.busy} onClick={() => setRemoving(null)}>{t('Cancelar', 'Cancel')}</button><button className="p-button-danger" disabled={mutation.busy || (removing === 'all' && resetConfirmation !== 'DELETE MY MEMORIES')} onClick={() => void mutation.run(() => removing === 'all' ? write('/settings/memories/reset', 'POST', { confirmation: resetConfirmation }) : write(`/settings/memories/${encodeURIComponent(removing)}`, 'DELETE'), () => setRemoving(null))}>{t('Eliminar definitivamente', 'Permanently delete')}</button></div></section>}
    <ActionState {...mutation}/>
  </div>;
}
