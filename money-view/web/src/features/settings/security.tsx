import { useState } from 'react';
import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import { Field } from '../../platform/ui';
import { dateText, sessionsSchema, type Settings, type Text } from './contracts';
import { ActionState, LoadState, SaveButton, useMutation, write } from './shared';

export function Security({ settings, t, locale, onChanged }: { settings: Settings; t: Text; locale: string; onChanged: () => void }) {
  const sessions = useResource(() => request('/settings/sessions', sessionsSchema), []);
  const mutation = useMutation(t, () => { sessions.reload(); onChanged(); });
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [repeatPassword, setRepeatPassword] = useState('');
  const [validation, setValidation] = useState('');
  const [revoke, setRevoke] = useState<string | null>(null);
  const expired = () => window.dispatchEvent(new Event('clara:session-expired'));
  async function revokeSessions() {
    const result = revoke === 'all' || revoke === 'others'
      ? await write('/settings/sessions/revoke', 'POST', { scope: revoke })
      : revoke === 'logout' ? await write('/session/logout', 'POST')
        : await write(`/settings/sessions/${encodeURIComponent(revoke ?? '')}`, 'DELETE');
    if (result.logged_out) expired();
  }
  return <div className="p-stack">
    {settings.capabilities.local_passwords ? <>
    <p className="p-muted">{t('Esta contraseña protege tu acceso a la demo local. No uses la contraseña de tu banco. La autenticación de dos factores no está disponible.', 'This password protects your local demo access. Do not use your bank password. Two-factor authentication is not available.')}</p>
    <h3>{t('Cambiar contraseña', 'Change password')}</h3>
    <form className="p-stack" onSubmit={event => { event.preventDefault(); setValidation(''); if (newPassword !== repeatPassword) { setValidation(t('Las contraseñas nuevas no coinciden.', 'The new passwords do not match.')); return; } void mutation.run(() => write('/settings/password', 'POST', { current_password: currentPassword, new_password: newPassword }), expired); }}>
      <Field label={t('Contraseña actual', 'Current password')}><input type="password" autoComplete="current-password" required value={currentPassword} onChange={event => setCurrentPassword(event.target.value)}/></Field>
      <Field label={t('Nueva contraseña', 'New password')} help={t('Entre 10 y 128 caracteres. Se cerrarán todas tus sesiones.', '10 to 128 characters. All your sessions will end.')}><input type="password" autoComplete="new-password" minLength={10} maxLength={128} required value={newPassword} onChange={event => setNewPassword(event.target.value)}/></Field>
      <Field label={t('Repetir contraseña nueva', 'Repeat new password')}><input type="password" autoComplete="new-password" minLength={10} maxLength={128} required value={repeatPassword} onChange={event => setRepeatPassword(event.target.value)}/></Field>
      {validation && <p role="alert" className="p-error">{validation}</p>}<SaveButton busy={mutation.busy} t={t}>{t('Cambiar contraseña y cerrar sesiones', 'Change password and end sessions')}</SaveButton>
    </form>
    </> : <p className="p-muted">{t('Este espacio de invitado no tiene contraseña. Usa Conservar espacio para crear un acceso local y conservar tus registros.', 'This guest workspace has no password. Use Keep workspace to create local access and keep your records.')}</p>}
    <h3>{t('Sesiones activas', 'Active sessions')}</h3><LoadState {...sessions} retry={sessions.reload} t={t}/>
    {sessions.data?.items.map(session => <div key={session.id} className="settings-session"><div><strong>{session.current ? t('Este navegador', 'This browser') : t('Otra sesión local', 'Other local session')}</strong><p className="p-muted">{t('Última actividad', 'Last active')}: {dateText(session.last_seen_at, locale)}</p><p className="p-muted">{t('Vence', 'Expires')}: {dateText(session.expires_at, locale)}</p></div><button className="p-button-secondary" disabled={mutation.busy} onClick={() => setRevoke(session.id)}>{t('Cerrar sesión', 'End session')}</button></div>)}
    <div className="p-actions"><button className="p-button-secondary" onClick={() => setRevoke('others')}>{t('Cerrar las otras sesiones', 'End other sessions')}</button><button className="p-button-secondary" onClick={() => setRevoke('all')}>{t('Cerrar todas las sesiones', 'End all sessions')}</button><button className="p-button-secondary" onClick={() => setRevoke('logout')}>{t('Salir de este navegador', 'Sign out of this browser')}</button></div>
    {revoke && <section className="settings-confirm" aria-label={t('Confirmar cierre de sesión', 'Confirm ending session')}><p>{settings.guest.is_guest ? t('Cerrar esta sesión puede hacerte perder el acceso a este espacio de invitado. Guarda el espacio antes de salir si quieres conservar el acceso.', 'Ending this session may lose access to this guest workspace. Save the workspace before leaving if you want to keep access.') : t('La sesión seleccionada dejará de tener acceso. Podrás entrar de nuevo con tu contraseña local.', 'The selected session will lose access. You can sign in again with your local password.')}</p><div className="p-actions"><button autoFocus className="p-button-secondary" disabled={mutation.busy} onClick={() => setRevoke(null)}>{t('Cancelar', 'Cancel')}</button><button className="p-button-danger" disabled={mutation.busy} onClick={() => void mutation.run(revokeSessions, () => setRevoke(null))}>{t('Confirmar cierre', 'Confirm sign out')}</button></div></section>}
    <ActionState {...mutation}/>
  </div>;
}
