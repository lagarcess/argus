import { useState } from 'react';
import { z } from 'zod';
import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import type { PlatformPageProps } from '../../platform/types';
import { Field, Modal, PageHeader, Panel } from '../../platform/ui';
import { householdSchema, membersSchema, settingsSchema } from './contracts';
import { ActionState, LoadState, SaveButton, useMutation, write } from './shared';

const createdMemberSchema = z.object({
  user_id: z.string(),
  display_name: z.string(),
  role: z.enum(['owner', 'editor', 'viewer']),
  local_only: z.literal(true),
});

export function HouseholdPage({ locale, revision, onChanged, onNavigate }: PlatformPageProps) {
  const t = (es: string, en: string) => locale === 'en' ? en : es;
  const resource = useResource(() => Promise.all([request('/settings', settingsSchema), request('/household/members', membersSchema), request('/households', z.object({ items: z.array(householdSchema) }))]), [revision]);
  const mutation = useMutation(t, () => { resource.reload(); onChanged(); });
  const [editor, setEditor] = useState<'name' | 'add' | null>(null);
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'owner' | 'editor' | 'viewer'>('viewer');
  const [removing, setRemoving] = useState<{ user_id: string; display_name: string } | null>(null);
  const [confirmName, setConfirmName] = useState('');
  const [createdMember, setCreatedMember] = useState<z.infer<typeof createdMemberSchema> | null>(null);
  const [copyStatus, setCopyStatus] = useState<'copied' | 'unavailable' | null>(null);
  const settings = resource.data?.[0];
  const owner = settings?.household.role === 'owner';
  const roles = { owner: t('Propietario/a', 'Owner'), editor: t('Editor/a', 'Editor'), viewer: t('Solo lectura', 'Viewer') };
  async function saveEditor() {
    if (editor === 'name') {
      await write('/household', 'PATCH', { name: name.trim() });
      return;
    }
    const member = await request('/household/members', createdMemberSchema, {
      method: 'POST', body: JSON.stringify({ display_name: name.trim(), password, role }),
    });
    setCreatedMember(member);
    setCopyStatus(null);
    setPassword('');
  }
  async function copyLoginId() {
    if (!createdMember) return;
    try {
      await navigator.clipboard.writeText(createdMember.user_id);
      setCopyStatus('copied');
    } catch {
      setCopyStatus('unavailable');
    }
  }
  return <div className="settings-page"><PageHeader title={t('Tu hogar', 'Your household')} description={t('Personas y preferencias que comparten tus registros de demostración.', 'People and preferences that share your demonstration records.')}/><LoadState {...resource} retry={resource.reload} t={t}/>{resource.data && settings && <>
    {createdMember && <Panel className="p-stack" aria-label={t('Cuenta local creada', 'Local account created')}>
      <h2>{t('Cuenta local creada', 'Local account created')}: {createdMember.display_name}</h2>
      <p>{t('Rol al crear la cuenta', 'Role when created')}: {roles[createdMember.role]}</p>
      <Field label={t('Identificador de acceso local', 'Local login ID')}><input readOnly value={createdMember.user_id} onFocus={event => event.target.select()}/></Field>
      <div className="p-actions"><button type="button" className="p-button-secondary" onClick={() => void copyLoginId()}>{t('Copiar identificador', 'Copy login ID')}</button></div>
      {copyStatus && <p className="p-muted" role="status">{copyStatus === 'copied' ? t('Identificador copiado.', 'Login ID copied.') : t('No se pudo copiar. Selecciona el identificador y cópialo manualmente.', 'Could not copy. Select the login ID and copy it manually.')}</p>}
      <p>{t('Para entrar con esta cuenta, cierra tu sesión, elige «Usar un identificador local» e introduce este identificador y la contraseña local que acabas de elegir.', 'To sign in with this account, sign out, choose “Use a local account ID”, and enter this ID and the local password you just chose.')}</p>
      <p className="p-muted">{t('El acceso es solo para esta demo local. No se envía ninguna invitación por correo. El identificador también queda disponible en la lista de personas.', 'Access is only for this local demo. No email invitation is sent. The ID also remains available in the member list.')}</p>
      <button className="p-button-ghost" onClick={() => onNavigate('settings', { panel: 'security' })}>{t('Ir a seguridad para cerrar sesión', 'Go to security to sign out')}</button>
    </Panel>}
    <Panel><div className="settings-session"><div><h2>{settings.household.name}</h2><p className="p-muted">{settings.household.country} · {settings.household.effective_currency} · {roles[settings.household.role]}</p></div>{owner && <button className="p-button-secondary" onClick={() => { setName(settings.household.name); setEditor('name'); }}>{t('Editar nombre', 'Edit name')}</button>}</div><p className="p-muted">{t('Los miembros ven los mismos registros del hogar. Las personas con solo lectura no pueden cambiarlos.', 'Members see the same household records. Viewers cannot change them.')}</p>{resource.data[2].items.length > 1 && <Field label={t('Cambiar de hogar', 'Switch household')}><select value={settings.household.id} disabled={mutation.busy} onChange={event => void mutation.run(() => write('/households/switch', 'POST', { household_id: event.target.value }))}>{resource.data[2].items.map(household => <option key={household.id} value={household.id}>{household.name}</option>)}</select></Field>}<button className="p-button-ghost" onClick={() => onNavigate('settings', { panel: 'regional' })}>{t('País y moneda', 'Country and currency')}</button></Panel>
    <Panel><div className="settings-session"><h2>{t('Personas', 'Members')}</h2>{owner && <button className="p-button" onClick={() => { setName(''); setPassword(''); setRole('viewer'); setEditor('add'); }}>{t('Agregar persona demo', 'Add demo member')}</button>}</div>{resource.data[1].items.map(member => <div className="settings-member" key={member.user_id}><div className={`settings-avatar ${member.avatar_color}`} aria-hidden="true">{member.display_name.slice(0, 1)}</div><div className="settings-member-name"><strong>{member.display_name}</strong><p className="p-muted">{member.user_id === settings.profile.id ? t('Tú', 'You') : roles[member.role]}</p>{owner && <details><summary>{t('Identificador de acceso local', 'Local login ID')}</summary><code className="settings-login-id">{member.user_id}</code></details>}</div>{owner ? <div className="p-actions"><label className="settings-role"><span className="sr-only">{t('Rol de', 'Role for')} {member.display_name}</span><select aria-label={`${t('Rol de', 'Role for')} ${member.display_name}`} disabled={mutation.busy} value={member.role} onChange={event => void mutation.run(() => write(`/household/members/${encodeURIComponent(member.user_id)}`, 'PATCH', { role: event.target.value }))}>{Object.entries(roles).map(([value, title]) => <option key={value} value={value}>{title}</option>)}</select></label><button className="p-button-ghost" disabled={mutation.busy} onClick={() => { setRemoving(member); setConfirmName(''); }}>{t('Quitar', 'Remove')}</button></div> : <span className="p-muted">{roles[member.role]}</span>}</div>)}</Panel>
    <Panel><h2>{t('Más para tu hogar', 'More for your household')}</h2><div className="p-actions"><button className="p-button-secondary" onClick={() => onNavigate('membership')}>{t('Membresía', 'Membership')}</button><button className="p-button-secondary" onClick={() => onNavigate('employer')}>{t('Beneficios de empresa', 'Employer benefits')}</button></div></Panel>
  </>}{!editor && !removing && <ActionState {...mutation}/>}
    {editor && <Modal title={editor === 'name' ? t('Nombre del hogar', 'Household name') : t('Agregar persona demo', 'Add demo member')} onClose={() => { if (!mutation.busy) setEditor(null); }}><form className="p-stack" onSubmit={event => { event.preventDefault(); void mutation.run(saveEditor, () => setEditor(null)); }}><Field label={t('Nombre', 'Name')}><input required maxLength={80} value={name} onChange={event => setName(event.target.value)}/></Field>{editor === 'add' && <><p className="p-muted">{t('Crea un acceso en esta demo local. No se envía ninguna invitación.', 'Creates access in this local demo. No invitation is sent.')}</p><Field label={t('Contraseña local', 'Local password')} help={t('Entre 10 y 128 caracteres. No uses una contraseña real.', '10 to 128 characters. Do not use a real password.')}><input required type="password" minLength={10} maxLength={128} autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)}/></Field><Field label={t('Rol', 'Role')}><select value={role} onChange={event => setRole(event.target.value as typeof role)}>{Object.entries(roles).map(([value, title]) => <option key={value} value={value}>{title}</option>)}</select></Field></>}<ActionState {...mutation}/><div className="p-actions"><button className="p-button-secondary" type="button" disabled={mutation.busy} onClick={() => setEditor(null)}>{t('Cancelar', 'Cancel')}</button><SaveButton busy={mutation.busy} t={t}/></div></form></Modal>}
    {removing && <Modal destructive title={t('Quitar del hogar', 'Remove from household')} onClose={() => { if (!mutation.busy) setRemoving(null); }}><form className="p-stack" onSubmit={event => { event.preventDefault(); void mutation.run(() => write(`/household/members/${encodeURIComponent(removing.user_id)}`, 'DELETE'), () => setRemoving(null)); }}><p>{t('Esta persona perderá acceso a este hogar y se eliminarán sus recuerdos y comentarios aquí. Si no pertenece a otro hogar, también se eliminarán su cuenta local y sus sesiones. Los registros financieros compartidos se conservan.', 'This person will lose household access and their memories and feedback here will be deleted. If they belong to no other household, their local account and sessions will also be deleted. Shared financial records remain.')}</p><Field label={t(`Escribe ${removing.display_name} para confirmar`, `Type ${removing.display_name} to confirm`)}><input value={confirmName} onChange={event => setConfirmName(event.target.value)}/></Field><ActionState {...mutation}/><div className="p-actions"><button autoFocus data-modal-cancel type="button" className="p-button-secondary" disabled={mutation.busy} onClick={() => setRemoving(null)}>{t('Cancelar', 'Cancel')}</button><button className="p-button-danger" disabled={mutation.busy || confirmName !== removing.display_name}>{t('Quitar persona', 'Remove member')}</button></div></form></Modal>}
  </div>;
}
