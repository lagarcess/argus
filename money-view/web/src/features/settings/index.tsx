import { useEffect, useRef } from 'react';
import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import type { PlatformPageProps } from '../../platform/types';
import { Modal, PageHeader } from '../../platform/ui';
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
type SectionName = 'account' | 'preferences' | 'data' | 'help';
type SettingsSection = { id: SectionName; title: string; description: string; panels: PanelName[] };

export function SettingsPage({ locale, revision, query, onChanged, onNavigate }: PlatformPageProps) {
  const t = (es: string, en: string) => locale === 'en' ? en : es;
  const resource = useResource(() => request('/settings', settingsSchema), []);
  const previousRevision = useRef(revision);
  const sectionHeading = useRef<HTMLHeadingElement>(null);
  const sectionButtons = useRef<Record<string, HTMLButtonElement | null>>({});
  const previousSection = useRef(query.get('section'));
  useEffect(() => {
    if (previousRevision.current !== revision) {
      previousRevision.current = revision;
      resource.reload();
    }
  }, [revision, resource.reload]);
  const requestedSection = query.get('section');
  useEffect(() => {
    if (requestedSection !== previousSection.current) {
      const previous = previousSection.current;
      previousSection.current = requestedSection;
      if (requestedSection) sectionHeading.current?.focus();
      else if (previous) sectionButtons.current[previous]?.focus();
    }
  }, [requestedSection]);
  const settings = resource.data;
  const titles: Record<PanelName, string> = {
    profile: t('Perfil', 'Profile'), language: t('Idioma', 'Language'),
    regional: t('País, moneda y zona horaria', 'Country, currency and time zone'),
    appearance: t('Apariencia', 'Appearance'), notifications: t('Notificaciones', 'Notifications'),
    security: t('Seguridad y sesiones', 'Security and sessions'), memories: t('Recuerdos confirmados', 'Confirmed memories'),
    usage: t('Uso local', 'Local usage'), data: t('Controles de datos', 'Data controls'),
    archived: t('Conversaciones archivadas', 'Archived conversations'), trashed: t('Eliminados recientemente', 'Recently deleted'),
    feedback: t('Comentarios', 'Feedback'), guide: t('Guía de Argus', 'Argus guide'), privacy: t('Privacidad', 'Privacy'),
    terms: t('Condiciones', 'Terms'), shortcuts: t('Atajos de teclado', 'Keyboard shortcuts'), receipts: t('Recibos y exportaciones', 'Receipts and exports'),
  };
  // Like Argus ProfileSettingsPanels, each leaf has one parent in this registry.
  const sections: SettingsSection[] = [
    { id: 'account', title: t('Cuenta y hogar', 'Account and household'), description: t('Perfil, accesos y personas', 'Profile, access and members'), panels: ['profile', 'security'] },
    { id: 'preferences', title: t('Preferencias', 'Preferences'), description: t('Idioma, apariencia y moneda', 'Language, appearance and currency'), panels: ['language', 'regional', 'appearance', 'notifications'] },
    { id: 'data', title: t('Datos y personalización', 'Data and personalization'), description: t('Recuerdos, historial y exportaciones', 'Memories, history and exports'), panels: ['memories', 'usage', ...(settings?.capabilities.archive_conversations === true ? ['archived' as const, 'trashed' as const] : []), 'receipts', 'data'] },
    { id: 'help', title: t('Ayuda e información', 'Help and information'), description: t('Comentarios, guía y privacidad', 'Feedback, guide and privacy'), panels: ['feedback', 'guide', 'shortcuts', 'privacy', 'terms'] },
  ];
  const selected = query.get('panel');
  const parentSection = sections.find(section => section.panels.includes(selected as PanelName));
  const active = parentSection ? selected as PanelName : null;
  const section = parentSection ?? sections.find(item => item.id === requestedSection) ?? sections[0];
  const hasSection = Boolean(parentSection || sections.some(item => item.id === requestedSection));
  const setActive = (panel: PanelName | null) => {
    const owner = panel ? sections.find(item => item.panels.includes(panel)) : section;
    onNavigate('settings', { section: owner?.id ?? section.id, ...(panel ? { panel } : {}) }, { replace: panel === null });
  };
  const appearance = settings && { light: t('Clara', 'Light'), dark: t('Oscura', 'Dark'), system: t('Según el dispositivo', 'Device setting') }[settings.preferences.appearance];
  const values: Partial<Record<PanelName, string>> = settings ? {
    profile: settings.profile.display_name,
    security: settings.guest.is_guest ? t('Acceso de invitado', 'Guest access') : t('Contraseña y accesos', 'Password and access'),
    language: settings.preferences.locale === 'en' ? 'English' : 'Español',
    regional: [settings.household.country, settings.household.effective_currency].filter(Boolean).join(' · ') || t('Sin seleccionar', 'Not selected'),
    appearance: appearance ?? '', notifications: t('Dentro de Argus', 'Inside Argus'),
    memories: `${new Intl.NumberFormat(locale).format(settings.memory.count)} · ${settings.memory.enabled ? t('Activados', 'Enabled') : t('Desactivados', 'Disabled')}`,
    usage: t('Registros guardados', 'Saved records'), receipts: t('Exportaciones locales', 'Local exports'),
    data: t('Exportar, restablecer o eliminar', 'Export, reset or delete'), feedback: t('Guardados localmente', 'Saved locally'),
  } : {};
  return <div className="settings-page" data-settings-panel={active ?? undefined}>
    <PageHeader title={t('Configuración', 'Settings')} description={t('Tu perfil, tus preferencias y el control de tus datos.', 'Your profile, preferences and control over your data.')}/>
    <LoadState {...resource} retry={resource.reload} t={t}/>
    {settings && <>
      <div className="settings-identity"><span className={`settings-avatar ${settings.profile.avatar_color}`} aria-hidden="true">{settings.profile.display_name.slice(0, 1)}</span><div><strong>{settings.profile.display_name}</strong><p className="p-muted">{settings.household.name} · {t('Espacio local', 'Local workspace')}</p></div></div>
      <div className="settings-workspace" data-section-open={hasSection}>
        <nav className="settings-section-nav" aria-label={t('Secciones de configuración', 'Settings sections')}>
          {sections.map(item => <button key={item.id} ref={element => { sectionButtons.current[item.id] = element; }} className="settings-section-link" aria-current={section.id === item.id && hasSection ? 'page' : undefined} onClick={() => onNavigate('settings', { section: item.id })}><span><strong>{item.title}</strong><small>{item.description}</small></span><span aria-hidden="true">›</span></button>)}
        </nav>
        <section className="settings-section-detail" aria-labelledby="settings-section-title">
          <button className="p-button-ghost settings-section-back" onClick={() => onNavigate('settings')}>‹ {t('Volver a configuración', 'Back to settings')}</button>
          <h2 id="settings-section-title" tabIndex={-1} ref={sectionHeading}>{section.title}</h2>
          <div className="settings-section-rows">{section.panels.map(panel => <Row key={panel} title={titles[panel]} value={values[panel]} onClick={() => setActive(panel)}/>)}</div>
          {section.id === 'account' && <Row title={t('Tu hogar', 'Your household')} value={settings.household.name} onClick={() => onNavigate('household')}/>}
        </section>
      </div>
      {active && <Modal key={active} historyMode="route" title={titles[active]} onClose={() => setActive(null)}>
        <button className="p-button-ghost settings-back" onClick={() => setActive(null)}>‹ {section.title}</button>
        {(['profile', 'language', 'regional', 'appearance', 'notifications'] as string[]).includes(active) && <Preferences key={active} panel={active as PreferencePanel} settings={settings} t={t} onChanged={onChanged} onClose={() => setActive(null)}/>}
        {active === 'security' && <Security settings={settings} t={t} locale={locale} onChanged={onChanged}/>}
        {active === 'memories' && <Memories t={t} locale={locale} onChanged={onChanged}/>}
        {active === 'usage' && <Usage t={t} locale={locale}/>}
        {active === 'data' && <DataControls t={t} settings={settings} onChanged={onChanged}/>}
        {(active === 'archived' || active === 'trashed') && <ConversationRecovery state={active} t={t} locale={locale} onChanged={onChanged}/>}
        {active === 'feedback' && <Feedback t={t} locale={locale} onChanged={onChanged}/>}
        {(['guide', 'privacy', 'terms', 'shortcuts'] as string[]).includes(active) && <Help section={active as 'guide' | 'privacy' | 'terms' | 'shortcuts'} t={t}/>}
        {active === 'receipts' && <div className="p-stack"><p>{t('Tus resultados guardados conservan sus supuestos. Puedes abrirlos desde Guardados y exportar los registros del hogar como JSON. Argus no publica enlaces compartidos en este espacio local.', 'Your saved results retain their assumptions. Open them from Saved and export household records as JSON. Argus does not publish shared links in this local workspace.')}</p><button className="p-button-secondary" onClick={() => onNavigate('saved')}>{t('Abrir guardados', 'Open saved')}</button><button className="p-button-secondary" onClick={() => setActive('data')}>{t('Exportar datos del hogar', 'Export household data')}</button></div>}
      </Modal>}
    </>}
  </div>;
}
