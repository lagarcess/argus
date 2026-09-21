import { useState } from 'react';
import { z } from 'zod';
import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import { Field } from '../../platform/ui';
import { dateText, feedbackSchema, type Text } from './contracts';
import { ActionState, LoadState, SaveButton, useMutation } from './shared';

export function Feedback({ t, locale, onChanged }: { t: Text; locale: string; onChanged: () => void }) {
  const resource = useResource(() => request('/settings/feedback', z.object({ items: z.array(feedbackSchema) })), []);
  const mutation = useMutation(t, () => { resource.reload(); onChanged(); });
  const [kind, setKind] = useState('general');
  const [message, setMessage] = useState('');
  return <div className="p-stack"><p className="p-muted">{t('Tus comentarios se guardan en esta demo local. No se envían a un equipo de soporte.', 'Your feedback is saved in this local demo. It is not sent to a support team.')}</p><form className="p-stack" onSubmit={event => { event.preventDefault(); void mutation.run(() => request('/settings/feedback', feedbackSchema, { method: 'POST', body: JSON.stringify({ kind, message: message.trim() }) }), () => setMessage('')); }}><Field label={t('Tipo de comentario', 'Feedback type')}><select value={kind} onChange={event => setKind(event.target.value)}><option value="general">{t('Comentario general', 'General feedback')}</option><option value="bug">{t('Reportar un problema', 'Report a problem')}</option><option value="feature">{t('Sugerir una función', 'Suggest a feature')}</option></select></Field><Field label={t('Tu comentario', 'Your feedback')}><textarea rows={5} required minLength={1} maxLength={5000} value={message} onChange={event => setMessage(event.target.value)}/></Field><SaveButton busy={mutation.busy} t={t}>{t('Guardar comentario local', 'Save local feedback')}</SaveButton></form><ActionState {...mutation}/><h3>{t('Comentarios guardados', 'Saved feedback')}</h3><LoadState {...resource} retry={resource.reload} t={t}/>{resource.data?.items.map(item => <article key={item.id} className="settings-memory"><p>{item.message}</p><small className="p-muted">{t('Guardado localmente', 'Saved locally')} · {dateText(item.created_at, locale)} · {item.id}</small></article>)}</div>;
}

const helpSchema = z.object({ local_only: z.boolean(), documents: z.array(z.object({ id: z.string(), title_key: z.string(), body_key: z.string() })), shortcuts: z.array(z.object({ keys: z.array(z.string()), action_key: z.string() })) });
export function Help({ section, t }: { section: 'guide' | 'privacy' | 'terms' | 'shortcuts'; t: Text }) {
  const resource = useResource(() => request('/settings/help', helpSchema), []);
  const copy: Record<string, string> = {
    'help.guide.title': t('Cómo usar Clara', 'How to use Clara'),
    'help.guide.body': t('Empieza en Cuentas para revisar tus registros de ejemplo. Movimientos permite categorizar y dividir gastos; Presupuestos y Metas guardan tus planes. Los escenarios calculan resultados con tus supuestos. Preguntar a Clara explica los mismos datos. Las fuentes y fechas acompañan los resultados. Todos los servicios externos son simulaciones locales.', 'Start in Accounts to review your example records. Transactions lets you categorize and split spending; Budgets and Goals save your plans. Scenarios calculate outcomes using your assumptions. Ask Clara explains the same data. Sources and dates accompany results. All external services are local simulations.'),
    'help.privacy.title': t('Privacidad de la demo', 'Demo privacy'),
    'help.privacy.body': t('Clara guarda perfiles, preferencias y registros en una base de datos del servidor local. Las cookies de sesión permiten entrar a tu cuenta local. Los recuerdos solo se usan cuando los confirmas y activas. Puedes exportar tus datos o eliminar tu cuenta desde Controles de datos. No introduzcas credenciales bancarias ni datos sensibles reales. Esta explicación describe la demo y no constituye una política de un servicio público.', 'Clara stores profiles, preferences and records in a database on the local server. Session cookies provide access to your local account. Memories are used only when you confirm and enable them. You can export your data or delete your account from Data controls. Do not enter bank credentials or real sensitive data. This explains the demo and is not a public service privacy policy.'),
    'help.terms.title': t('Condiciones de la demo', 'Demo terms'),
    'help.terms.body': t('Clara es una demostración educativa. Los datos simulados no representan tus cuentas reales. Las operaciones, citas, membresías, beneficios y documentos son simulaciones: no ejecutan pagos, inversiones, contrataciones ni trámites. Los cálculos dependen de los supuestos mostrados y no son recomendaciones financieras, fiscales o legales.', 'Clara is an educational demonstration. Simulated data does not represent your real accounts. Orders, appointments, memberships, benefits and documents are simulations: they do not execute payments, investments, contracts or filings. Calculations depend on the displayed assumptions and are not financial, tax or legal recommendations.'),
    'help.shortcuts.close': t('Cerrar el panel abierto', 'Close the open panel'),
  };
  return <div className="p-stack"><LoadState {...resource} retry={resource.reload} t={t}/>{section === 'shortcuts' ? resource.data?.shortcuts.map(item => <div className="settings-session" key={item.action_key}><kbd>{item.keys.join(' + ')}</kbd><span>{copy[item.action_key] ?? t('Atajo disponible', 'Available shortcut')}</span></div>) : resource.data?.documents.filter(document => document.id === section).map(document => <article key={document.id}><h3>{copy[document.title_key]}</h3><p>{copy[document.body_key]}</p></article>)}</div>;
}
