import { useState } from 'react';
import { z } from 'zod';
import { request } from '../../platform/client';
import { useResource } from '../../platform/hooks';
import { PageHeader,Panel,EvidenceLine,Money,EmptyState } from '../../platform/ui';
import { evidenceSchema,type PlatformPageProps } from '../../platform/types';
import { text,Recorded,timeLabel,Loading,EditDialog,ConfirmDialog,DownloadLink,uniqueKey,useAction } from './shared';
const membershipSchema=z.object({ plans: z.array(z.object({ id: z.string(),amount: z.string(),currency: z.string(),interval: z.string(),evidence: evidenceSchema })),membership: z.object({ plan_id: z.string(),status: z.string(),recorded_at: z.string() }).nullable(),receipts: z.array(z.object({ id: z.string(),plan_id: z.string(),amount: z.string(),currency: z.string(),status: z.string(),recorded_at: z.string() })),mode: z.string() });
export function MembershipPage({ locale,revision,onChanged }: PlatformPageProps) {
  const t=(es: string,en: string) => text(locale,es,en);
  const resource=useResource(() => request('/membership',membershipSchema),[revision]);
  const [selection,setSelection]=useState<{
    id: string;
    key: string;
  }|null>(null);
  const [cancel,setCancel]=useState(false);
  const d=resource.data;
  const changed=() => { resource.reload(); onChanged(); };
  const plan=d?.plans.find(p => p.id===selection?.id);
  return <div className="p-stack services-page">
    <PageHeader eyebrow={t('MEMBRESÍA','MEMBERSHIP')} title={t('Un espacio para tu dinero.','A space for your money.')} description={t('Explora planes y conserva un recibo local. Esta demo no cobra ni pide una tarjeta.','Explore plans and keep a local receipt. This demo does not charge or request a card.')} />
    <Loading locale={locale} {...resource} retry={resource.reload} />
    {d&&<>
      <Panel>
        <div className="p-toolbar">
          <div>
            <span className="p-badge">
              {t('SIMULACIÓN SIN COBRO','SIMULATION WITH NO CHARGE')}
            </span>
            <h2>
              {d.membership?.status==='active'? t('Tu membresía está activa en la demo','Your demo membership is active'):t('Tu acceso de demostración','Your demonstration access')}
            </h2>
            {d.membership&&<>
              <p>
                {d.membership.plan_id==='annual'? t('Plan anual','Annual plan'):t('Plan mensual','Monthly plan')} · {d.membership.status==='active'? t('Activo','Active'):t('Cancelado','Cancelled')}
              </p>
              <Recorded locale={locale} at={d.membership.recorded_at} />
            </>}
          </div>
          {d.membership?.status==='active'&&
            <button className="p-button-secondary" onClick={() => setCancel(true)}>
              {t('Cancelar membresía demo','Cancel demo membership')}
            </button>
          }
        </div>
      </Panel>
      <div className="services-columns">
        {d.plans.map(p =>
          <Panel key={p.id}>
            <span className="p-badge">
              {t('PLAN DE EJEMPLO','SAMPLE PLAN')}
            </span>
            <h2>
              {p.interval==='year'? t('Un año de claridad','A year of clarity'):t('Mes a mes','Month by month')}
            </h2>
            <p className="services-price">
              <Money amount={p.amount} currency={p.currency} locale={locale} />
              <small>
                / {p.interval==='year'? t('año','year'):t('mes','month')}
              </small>
            </p>
            <EvidenceLine locale={locale} evidence={p.evidence} />
            <p>
              {t('Organización de cuentas, escenarios guardados y seguimiento en este entorno local.','Account organization, saved scenarios and tracking in this local environment.')}
            </p>
            <button className="p-button" disabled={d.membership?.status==='active'&&d.membership.plan_id===p.id} onClick={() => setSelection({ id: p.id,key: uniqueKey() })}>
              {d.membership?.status==='active'&&d.membership.plan_id===p.id? t('Plan actual','Current plan'):t('Simular este plan','Simulate this plan')}
            </button>
          </Panel>
        )}
      </div>
      <Panel>
        <h2>
          {t('Recibos de la demostración','Demonstration receipts')}
        </h2>
        {d.receipts.length===0?
          <EmptyState title={t('Aún no hay recibos','No receipts yet')} description={t('Al simular un plan, el recibo aparecerá aquí.','A receipt appears here when you simulate a plan.')} />
          :d.receipts.map(r =>
            <article className="services-detail-row" key={r.id}>
              <div>
                <strong>
                  {r.plan_id==='annual'? t('Plan anual','Annual plan'):t('Plan mensual','Monthly plan')}
                </strong>
                <p className="p-muted">
                  {r.id}
                </p>
              </div>
              <div>
                <Money amount={r.amount} currency={r.currency} locale={locale} />
                <p className="p-badge">
                  {t('Simulado · sin cargo','Simulated · no charge')}
                </p>
              </div>
              <Recorded locale={locale} at={r.recorded_at} />
            </article>
          )}
      </Panel>
    </>}{selection&&plan&&
      <ConfirmDialog locale={locale} title={t('Simular membresía','Simulate membership')} path="/membership" payload={{ plan_id: selection.id,request_key: selection.key }} onClose={() => setSelection(null)} onSaved={changed}>
        <p>
          {t('Se guardará una membresía y un recibo de ejemplo. No habrá cargos ni renovación real.','A sample membership and receipt will be saved. There are no charges or real renewals.')}
        </p>
        <Money amount={plan.amount} currency={plan.currency} locale={locale} />
        <EvidenceLine evidence={plan.evidence} locale={locale} />
      </ConfirmDialog>
    }{cancel&&
      <ConfirmDialog locale={locale} title={t('Cancelar membresía demo','Cancel demo membership')} path="/membership/cancel" onClose={() => setCancel(false)} onSaved={changed} destructive>
        <p>
          {t('La membresía local quedará cancelada. Tus recibos anteriores se conservan.','The local membership will be cancelled. Existing receipts are retained.')}
        </p>
      </ConfirmDialog>
    }
  </div>
    ;
}
const appointmentsSchema=z.object({ specialists: z.array(z.object({ id: z.string(),name: z.string(),specialty: z.string(),demo: z.boolean() })),slots: z.array(z.object({ id: z.string(),specialist_id: z.string(),starts_at: z.string(),ends_at: z.string(),available: z.boolean() })),reservations: z.array(z.object({ id: z.string(),slot_id: z.string(),status: z.string(),recorded_at: z.string() })),mode: z.string() });
export function HelpPage({ locale,revision,onChanged }: PlatformPageProps) {
  const t=(es: string,en: string) => text(locale,es,en);
  const resource=useResource(() => request('/appointments',appointmentsSchema),[revision]);
  const [selection,setSelection]=useState<{
    id: string;
    key: string;
  }|null>(null);
  const [cancel,setCancel]=useState<string|null>(null);
  const [reschedule,setReschedule]=useState<string|null>(null);
  const d=resource.data;
  const changed=() => { resource.reload(); onChanged(); };
  const selectedSlot=d?.slots.find(s => s.id===selection?.id);
  const available=d?.slots.filter(s => s.available)||[];
  return <div className="p-stack services-page">
    <PageHeader eyebrow={t('ACOMPAÑAMIENTO','HUMAN HELP')} title={t('Prepara una conversación.','Prepare a conversation.')} description={t('Explora horarios y organiza una sesión de ejemplo. No se contacta a nadie ni se reserva una cita real.','Explore times and organize a sample session. Nobody is contacted and no real appointment is booked.')} />
    <Loading locale={locale} {...resource} retry={resource.reload} />
    {d&&<>
      <Panel>
        <h2>
          {t('Tu agenda local','Your local agenda')}
        </h2>
        {d.reservations.length===0?
          <EmptyState title={t('Sin sesiones en tu agenda','No sessions in your agenda')} description={t('Elige un horario disponible para probar la reserva.','Choose an available time to try a reservation.')} />
          :d.reservations.map(r => {
            const slot=d.slots.find(s => s.id===r.slot_id); const specialist=d.specialists.find(s => s.id===slot?.specialist_id); return <article className="services-account" key={r.id}>
              <div className="p-toolbar">
                <h3>
                  {specialist?.name||t('Sesión local','Local session')}
                </h3>
                <span className="p-badge">
                  {r.status==='cancelled'? t('Cancelada','Cancelled'):t('Reservada en demo','Reserved in demo')}
                </span>
              </div>
              <p>
                {slot? `${timeLabel(slot.starts_at,locale)} · ${t('hora local','local time')}`:t('Horario no disponible','Time unavailable')}
              </p>
              <Recorded locale={locale} at={r.recorded_at} />
              {r.status!=='cancelled'&&
                <div className="p-actions">
                  <button className="p-button-secondary" disabled={!available.length} onClick={() => setReschedule(r.id)}>
                    {t('Cambiar horario','Change time')}
                  </button>
                  <button className="p-button-ghost" onClick={() => setCancel(r.id)}>
                    {t('Cancelar sesión','Cancel session')}
                  </button>
                  <DownloadLink path={`/appointments/${r.id}/calendar`}>
                    {t('Descargar calendario demo','Download demo calendar')}
                  </DownloadLink>
                </div>
              }
            </article>
              ;
          })}
      </Panel>
      <Panel>
        <div className="p-toolbar">
          <h2>
            {t('Horarios disponibles','Available times')}
          </h2>
          <span className="p-badge">
            {t('PERSONAS FICTICIAS','FICTIONAL PEOPLE')}
          </span>
        </div>
        {d.specialists.map(person =>
          <article className="services-account" key={person.id}>
            <h3>
              {person.name}
            </h3>
            <p className="p-muted">
              {person.specialty==='budgeting'? t('Presupuestos · especialista de ejemplo','Budgeting · sample specialist'):t('Organización documental · especialista de ejemplo','Document organization · sample specialist')}
            </p>
            <div className="services-slots">
              {d.slots.filter(s => s.specialist_id===person.id).map(s =>
                <button className="p-button-secondary" disabled={!s.available} key={s.id} onClick={() => setSelection({ id: s.id,key: uniqueKey() })}>
                  <span>
                    {timeLabel(s.starts_at,locale)}
                  </span>
                  <small>
                    {s.available? t('Reservar en demo','Reserve in demo'):t('No disponible','Unavailable')}
                  </small>
                </button>
              )}
            </div>
          </article>
        )}{!d.slots.length&&
          <EmptyState title={t('No hay horarios disponibles','No available times')} />
        }
        <p className="p-muted">
          {t('Las horas se muestran en la zona horaria de tu dispositivo. El calendario es un recibo local, sin invitaciones.','Times are shown in your device time zone. The calendar is a local receipt, with no invitations.')}
        </p>
      </Panel>
    </>}{selection&&selectedSlot&&
      <ConfirmDialog locale={locale} title={t('Guardar reserva local','Save local reservation')} path="/appointments" payload={{ slot_id: selection.id,request_key: selection.key }} onClose={() => setSelection(null)} onSaved={changed}>
        <p>
          {timeLabel(selectedSlot.starts_at,locale)}
        </p>
        <p>
          {t('Esta sesión es ficticia. No se enviarán invitaciones ni mensajes.','This session is fictional. No invitations or messages will be sent.')}
        </p>
      </ConfirmDialog>
    }{cancel&&
      <ConfirmDialog locale={locale} title={t('Cancelar sesión de ejemplo','Cancel sample session')} path={`/appointments/${cancel}/cancel`} onClose={() => setCancel(null)} onSaved={changed} destructive>
        <p>
          {t('El horario volverá a estar disponible en esta demo.','The time becomes available again in this demo.')}
        </p>
      </ConfirmDialog>
    }{reschedule&&
      <EditDialog locale={locale} title={t('Cambiar horario local','Change local time')} path={`/appointments/${reschedule}`} method="PATCH" fields={[{ name: 'slot_id',es: 'Nuevo horario',en: 'New time',options: available.map(s => ({ value: s.id,label: `${d?.specialists.find(p => p.id===s.specialist_id)?.name} · ${timeLabel(s.starts_at,locale)}` })) }]} onClose={() => setReschedule(null)} onSaved={changed} />
    }
  </div>
    ;
}
const employerSchema=z.object({ enrollment: z.object({ employer_id: z.string(),benefit_id: z.string().nullable(),status: z.string(),recorded_at: z.string() }).nullable(),demo_code: z.string(),benefits: z.array(z.object({ id: z.string(),title: z.string() })),mode: z.string() });
const benefitCopy: Record<string,[
  string,
  string,
  string,
  string
]>={ learning: ['Aprendizaje','Learning','Organiza tu aprendizaje financiero en la demo.','Organize financial learning in the demo.'],wellness: ['Bienestar','Wellness','Explora un beneficio de bienestar ilustrativo.','Explore an illustrative wellness benefit.'],planning: ['Planificación','Planning','Reserva espacio para revisar tus objetivos.','Make space to review your goals.'] };
export function EmployerPage({ locale,revision,onChanged }: PlatformPageProps) {
  const t=(es: string,en: string) => text(locale,es,en);
  const resource=useResource(() => request('/employer',employerSchema),[revision]);
  const [enroll,setEnroll]=useState(false);
  const [leave,setLeave]=useState(false);
  const d=resource.data;
  const changed=() => { resource.reload(); onChanged(); };
  const action=useAction(locale,changed);
  const active=d?.enrollment?.status==='enrolled';
  return <div className="p-stack services-page">
    <PageHeader eyebrow={t('BENEFICIOS LABORALES','EMPLOYER BENEFITS')} title={t('Un beneficio para organizarte.','A benefit to get organized.')} description={t('Prueba una inscripción local con un código de demostración. No se conecta con una empresa ni comparte información.','Try a local enrollment with a demonstration code. No employer is connected and no information is shared.')} />
    <Loading locale={locale} {...resource} retry={resource.reload} />
    {d&&<>
      <Panel>
        <div className="p-toolbar">
          <div>
            <span className="p-badge">
              {t('PROGRAMA LOCAL DE EJEMPLO','LOCAL SAMPLE PROGRAM')}
            </span>
            <h2>
              {active? t('Inscripción activa en la demo','Active demo enrollment'):t('Conoce el programa de ejemplo','Explore the sample program')}
            </h2>
            <p>
              {t('Código de prueba','Test code')}:
              <code>
                {d.demo_code}
              </code>
            </p>
            {d.enrollment&&
              <Recorded locale={locale} at={d.enrollment.recorded_at} />
            }
          </div>
          {active?
            <button className="p-button-secondary" onClick={() => setLeave(true)}>
              {t('Salir del programa demo','Leave demo program')}
            </button>
            :
            <button className="p-button" onClick={() => setEnroll(true)}>
              {t('Inscribirme en la demo','Enroll in the demo')}
            </button>
          }
        </div>
      </Panel>
      <Panel>
        <h2>
          {t('Elige un beneficio de ejemplo','Choose a sample benefit')}
        </h2>
        <p className="p-muted">
          {t('Tu selección se conserva en este hogar local. Puedes cambiarla después.','Your selection is retained in this local household. You can change it later.')}
        </p>
        {action.feedback}{d.benefits.map(b => {
          const copy=benefitCopy[b.id]; const chosen=active&&d.enrollment?.benefit_id===b.id; return <div className="services-benefit" key={b.id}>
            <div>
              <h3>
                {copy? copy[locale==='en'? 1:0]:t('Beneficio de ejemplo','Sample benefit')}
              </h3>
              <p>
                {copy?.[locale==='en'? 3:2]}
              </p>
            </div>
            <button className={chosen? 'p-button-ghost':'p-button-secondary'} disabled={!active||chosen||action.pending} onClick={() => void action.run('/employer/benefit','PUT',{ benefit_id: b.id })}>
              {chosen? t('Seleccionado','Selected'):t('Elegir beneficio','Choose benefit')}
            </button>
          </div>
            ;
        })}{!active&&
          <p className="p-muted">
            {t('Inscríbete con el código demo para seleccionar un beneficio.','Enroll with the demo code to choose a benefit.')}
          </p>
        }
      </Panel>
    </>}{enroll&&
      <EditDialog locale={locale} title={t('Inscripción de demostración','Demonstration enrollment')} path="/employer/enroll" fields={[{ name: 'code',es: 'Código del programa demo',en: 'Demo program code',help: t('Usa el código de prueba que aparece en la página.','Use the test code shown on the page.') }]} onClose={() => setEnroll(false)} onSaved={changed} submitLabel={t('Inscribirme localmente','Enroll locally')} />
    } {leave&&
      <ConfirmDialog locale={locale} title={t('Salir del programa demo','Leave demo program')} path="/employer/leave" onClose={() => setLeave(false)} onSaved={changed} destructive>
        <p>
          {t('Se cerrará esta inscripción local. Puedes volver a usar el código de prueba.','This local enrollment will end. You can use the test code again.')}
        </p>
      </ConfirmDialog>
    }
  </div>
    ;
}
