import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import type { PlatformPageProps } from '../../platform/types';
import { Modal, PageHeader, Panel } from '../../platform/ui';
import { settingsSchema } from './contracts';
import { ConversationRecovery, DataControls, Usage } from './data';
import { Memories } from './memories';
import { Preferences, type PreferencePanel } from './preferences';
import { Security } from './security';
import { LoadState, Row } from './shared';
import { Feedback, Help } from './support';
import './settings.css';

export { HouseholdPage } from './household';
type PanelName = PreferencePanel | 'security' | 'memories' | 'usage' | 'data' | 'archived' | 'trashed' | 'feedback' | 'guide' | 'privacy' | 'terms' | 'shortcuts' | 'receipts';

export function SettingsPage({ locale, revision, query, onChanged, onNavigate }: PlatformPageProps) {
  const t = (es: string, en: string) => locale === 'en' ? en : es;
  const resource = useResource(() => request('/settings', settingsSchema), []);
  const previousRevision = useRef(revision);
  useEffect(() => {
    if (previousRevision.current !== revision) {
      previousRevision.current = revision;
      resource.reload();
    }
  }, [revision, resource.reload]);
  const changed = onChanged;
  const titles: Record<PanelName, string> = { profile: t('Perfil', 'Profile'), language: t('Idioma', 'Language'), regional: t('País, moneda y zona horaria', 'Country, currency and time zone'), appearance: t('Apariencia', 'Appearance'), notifications: t('Notificaciones', 'Notifications'), security: t('Seguridad y sesiones', 'Security and sessions'), memories: t('Recuerdos confirmados', 'Confirmed memories'), usage: t('Uso local', 'Local usage'), data: t('Controles de datos', 'Data controls'), archived: t('Conversaciones archivadas', 'Archived conversations'), trashed: t('Eliminados recientemente', 'Recently deleted'), feedback: t('Comentarios', 'Feedback'), guide: t('Guía de Clara', 'Clara guide'), privacy: t('Privacidad', 'Privacy'), terms: t('Condiciones', 'Terms'), shortcuts: t('Atajos de teclado', 'Keyboard shortcuts'), receipts: t('Recibos y exportaciones', 'Receipts and exports') };
  const selected = query.get('panel');
  const active = selected && Object.hasOwn(titles, selected) ? selected as PanelName : null;
  const setActive = (panel: PanelName | null) => onNavigate('settings', panel ? { panel } : undefined);
  const settings = resource.data;
  const appearance = settings && { light: t('Clara', 'Light'), dark: t('Oscura', 'Dark'), system: t('Según el dispositivo', 'Device setting') }[settings.preferences.appearance];
  const select = (panel: PanelName, value?: string) => <Row key={panel} title={titles[panel]} value={value} onClick={() => setActive(panel)}/>;
  return <div className="settings-page" data-settings-panel={active ?? undefined}><PageHeader title={t('Configuración', 'Settings')} description={t('Tu perfil, tus preferencias y el control de tus datos.', 'Your profile, preferences and control over your data.')}/><LoadState {...resource} retry={resource.reload} t={t}/>{settings && <>
    <div className="settings-identity"><span className={`settings-avatar ${settings.profile.avatar_color}`} aria-hidden="true">{settings.profile.display_name.slice(0, 1)}</span><div><strong>{settings.profile.display_name}</strong><p className="p-muted">{settings.household.name} · {t('Cuenta de demostración local', 'Local demonstration account')}</p></div></div>
    <Panel><h2>{t('Cuenta y hogar', 'Account and household')}</h2>{select('profile', settings.profile.display_name)}{select('security', t('Contraseña y accesos', 'Password and access'))}<Row title={t('Tu hogar', 'Your household')} value={settings.household.name} onClick={() => onNavigate('household')}/></Panel>
    <Panel><h2>{t('Preferencias', 'Preferences')}</h2>{select('language', settings.preferences.locale === 'en' ? 'English' : 'Español')}{select('regional', `${settings.household.country} · ${settings.household.effective_currency}`)}{select('appearance', appearance || '')}{select('notifications', t('Dentro de Clara', 'Inside Clara'))}</Panel>
    <Panel><h2>{t('Datos y personalización', 'Data and personalization')}</h2>{select('memories', `${settings.memory.count} · ${settings.memory.enabled ? t('Activados', 'Enabled') : t('Desactivados', 'Disabled')}`)}{select('usage', t('Registros guardados', 'Saved records'))}{settings.capabilities.archive_conversations === true && <>{select('archived')}{select('trashed')}</>}{select('receipts', t('Exportaciones locales', 'Local exports'))}{select('data', t('Exportar, restablecer o eliminar', 'Export, reset or delete'))}</Panel>
    <Panel><h2>{t('Ayuda e información', 'Help and information')}</h2>{select('feedback', t('Guardados localmente', 'Saved locally'))}{select('guide')}{select('shortcuts')}{select('privacy')}{select('terms')}</Panel>
    {active && <Modal key={active} title={titles[active]} onClose={() => setActive(null)}><button className="p-button-ghost settings-back" onClick={() => setActive(null)}>‹ {t('Volver a configuración', 'Back to settings')}</button>
      {(['profile', 'language', 'regional', 'appearance', 'notifications'] as string[]).includes(active) && <Preferences key={active} panel={active as PreferencePanel} settings={settings} t={t} onChanged={changed} onClose={() => setActive(null)}/>}
      {active === 'security' && <Security t={t} locale={locale} onChanged={changed}/>}
      {active === 'memories' && <Memories t={t} locale={locale} onChanged={changed}/>}
      {active === 'usage' && <Usage t={t} locale={locale}/>}
      {active === 'data' && <DataControls t={t} settings={settings} onChanged={changed}/>}
      {(active === 'archived' || active === 'trashed') && <ConversationRecovery state={active} t={t} locale={locale} onChanged={changed}/>}
      {active === 'feedback' && <Feedback t={t} locale={locale} onChanged={changed}/>}
      {(['guide', 'privacy', 'terms', 'shortcuts'] as string[]).includes(active) && <Help section={active as 'guide' | 'privacy' | 'terms' | 'shortcuts'} t={t}/>}
      {active === 'receipts' && <div className="p-stack"><p>{t('Tus resultados guardados conservan sus supuestos. Puedes abrirlos desde Guardados y exportar los registros del hogar como JSON. Clara no publica enlaces compartidos en esta demo.', 'Your saved results retain their assumptions. Open them from Saved and export household records as JSON. Clara does not publish shared links in this demo.')}</p><button className="p-button-secondary" onClick={() => onNavigate('saved')}>{t('Abrir guardados', 'Open saved')}</button><button className="p-button-secondary" onClick={() => setActive('data')}>{t('Exportar datos del hogar', 'Export household data')}</button></div>}
    </Modal>}
  </>}</div>;
}
import { useEffect, useRef } from 'react';
