import { useState } from 'react';
import { Field } from '../../platform/ui';
import type { Settings, Text } from './contracts';
import { ActionState, SaveButton, useMutation, write } from './shared';

export type PreferencePanel = 'profile' | 'language' | 'regional' | 'appearance' | 'notifications';
export function Preferences({ panel, settings, t, onChanged, onClose }: { panel: PreferencePanel; settings: Settings; t: Text; onChanged: () => void; onClose: () => void }) {
  const [profile, setProfile] = useState(settings.profile);
  const [preferences, setPreferences] = useState(settings.preferences);
  const [household, setHousehold] = useState(settings.household);
  const mutation = useMutation(t, onChanged);
  const owner = settings.household.role === 'owner';
  async function save() {
    if (panel === 'profile') await write('/settings/profile', 'PATCH', { display_name: profile.display_name.trim(), preferred_name: profile.preferred_name?.trim() || null, avatar_color: profile.avatar_color });
    if (panel === 'language') await write('/settings/preferences', 'PATCH', { locale: preferences.locale });
    if (panel === 'appearance') await write('/settings/preferences', 'PATCH', { appearance: preferences.appearance, sidebar_compact: preferences.sidebar_compact });
    if (panel === 'notifications') await write('/settings/preferences', 'PATCH', { notifications: preferences.notifications });
    if (panel === 'regional') {
      await write('/settings/preferences', 'PATCH', { timezone: preferences.timezone });
      if (owner) await write('/household', 'PATCH', { country: household.country, currency_override: household.currency_override });
    }
  }
  return <form className="p-stack" onSubmit={event => { event.preventDefault(); void mutation.run(save, onClose); }}>
    {panel === 'profile' && <>
      <Field label={t('Nombre visible', 'Display name')}><input required maxLength={80} value={profile.display_name} onChange={event => setProfile({ ...profile, display_name: event.target.value })}/></Field>
      <Field label={t('Cómo quieres que te llamemos', 'Preferred name')} help={t('Opcional. Se usa en tus saludos.', 'Optional. Used in your greetings.')}><input maxLength={40} value={profile.preferred_name ?? ''} onChange={event => setProfile({ ...profile, preferred_name: event.target.value })}/></Field>
      <fieldset className="settings-choices"><legend>{t('Color del perfil', 'Profile color')}</legend>{(['forest', 'ocean', 'clay', 'gold', 'plum'] as const).map((color, index) => <label key={color}><input type="radio" name="avatar" value={color} checked={profile.avatar_color === color} onChange={() => setProfile({ ...profile, avatar_color: color })}/><span className={`settings-avatar ${color}`} aria-hidden="true"/>{[t('Bosque', 'Forest'), t('Océano', 'Ocean'), t('Arcilla', 'Clay'), t('Dorado', 'Gold'), t('Ciruela', 'Plum')][index]}</label>)}</fieldset>
    </>}
    {panel === 'language' && <fieldset className="settings-choices"><legend>{t('Idioma de Clara', 'Clara language')}</legend>{(['es-419', 'en'] as const).map(locale => <label key={locale}><input type="radio" name="locale" value={locale} checked={preferences.locale === locale} onChange={() => setPreferences({ ...preferences, locale })}/>{locale === 'en' ? 'English' : 'Español'}</label>)}</fieldset>}
    {panel === 'regional' && <>
      <Field label={t('Zona horaria', 'Time zone')} help={t('Por ejemplo: America/Santo_Domingo.', 'For example: America/Santo_Domingo.')}><input required list="clara-timezones" value={preferences.timezone} onChange={event => setPreferences({ ...preferences, timezone: event.target.value })}/></Field>
      <datalist id="clara-timezones">{['America/Santo_Domingo', 'America/New_York', 'America/Chicago', 'America/Los_Angeles', 'Europe/Madrid', 'Europe/London', 'Pacific/Auckland', 'Asia/Tokyo', 'UTC'].map(zone => <option key={zone} value={zone}/>)}</datalist>
      <Field label={t('País del hogar', 'Household country')}><select disabled={!owner} value={household.country} onChange={event => setHousehold({ ...household, country: event.target.value })}>{Object.entries({ DO: t('República Dominicana', 'Dominican Republic'), US: t('Estados Unidos', 'United States'), NZ: t('Nueva Zelanda', 'New Zealand'), ES: t('España', 'Spain'), GB: t('Reino Unido', 'United Kingdom'), CA: t('Canadá', 'Canada'), JP: t('Japón', 'Japan'), KW: t('Kuwait', 'Kuwait') }).map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></Field>
      <Field label={t('Moneda preferida', 'Preferred currency')} help={t('No convierte ni cambia la moneda de tus registros.', 'Does not convert or change the currency of your records.')}><select disabled={!owner} value={household.currency_override ?? ''} onChange={event => setHousehold({ ...household, currency_override: event.target.value || null })}><option value="">{t('Según el país', 'Use country default')}</option>{settings.supported_currencies.map(currency => <option key={currency}>{currency}</option>)}</select></Field>
      <p className="p-muted">{t('Moneda guardada actualmente', 'Current saved currency')}: {settings.household.effective_currency}</p>
      {!owner && <p className="p-muted">{t('Solo una persona propietaria cambia el país y la moneda del hogar.', 'Only an owner changes the household country and currency.')}</p>}
    </>}
    {panel === 'appearance' && <>
      <fieldset className="settings-choices"><legend>{t('Apariencia', 'Appearance')}</legend>{(['light', 'dark', 'system'] as const).map((appearance, index) => <label key={appearance}><input type="radio" name="appearance" checked={preferences.appearance === appearance} onChange={() => setPreferences({ ...preferences, appearance })}/>{[t('Clara', 'Light'), t('Oscura', 'Dark'), t('Según el dispositivo', 'Use device setting')][index]}</label>)}</fieldset>
      <label className="settings-check"><input type="checkbox" checked={preferences.sidebar_compact} onChange={event => setPreferences({ ...preferences, sidebar_compact: event.target.checked })}/>{t('Barra lateral compacta', 'Compact sidebar')}</label>
    </>}
    {panel === 'notifications' && <>
      <p className="p-muted">{t('Preferencias guardadas para avisos dentro de esta demo. No se envían correos ni notificaciones al dispositivo.', 'Saved preferences for notices inside this demo. No email or device notifications are sent.')}</p>
      {(['bills', 'account_changes', 'product_updates'] as const).map((key, index) => <label key={key} className="settings-check"><input type="checkbox" checked={preferences.notifications[key]} onChange={event => setPreferences({ ...preferences, notifications: { ...preferences.notifications, [key]: event.target.checked } })}/>{[t('Facturas y vencimientos', 'Bills and due dates'), t('Cambios en las cuentas', 'Account changes'), t('Novedades de Clara', 'Clara updates')][index]}</label>)}
    </>}
    <ActionState {...mutation}/><div className="p-actions"><button type="button" className="p-button-secondary" onClick={onClose} disabled={mutation.busy}>{t('Cancelar', 'Cancel')}</button><SaveButton busy={mutation.busy} t={t}/></div>
  </form>;
}
