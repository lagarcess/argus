import { useState,type ReactNode,type FormEvent } from 'react';
import { z } from 'zod';
import { request } from '../../platform/client';
import { Field,Modal } from '../../platform/ui';
import type { Locale } from '../../platform/types';
export const text=(locale: Locale,es: string,en: string) => locale==='en'? en:es;
export const today=() => new Date().toISOString().slice(0,10);
export const mutationSchema=z.record(z.string(), z.unknown());
export const dateLabel=(value: string,locale: Locale) => new Date(value.length===10? `${value}T12:00:00`:value).toLocaleDateString(locale==='en'? 'en-US':'es-DO',{ year: 'numeric',month: 'short',day: 'numeric' });
export const timeLabel=(value: string,locale: Locale) => new Date(value).toLocaleString(locale==='en'? 'en-US':'es-DO',{ dateStyle: 'medium',timeStyle: 'short' });
export const uniqueKey=() => crypto.randomUUID();
export function ErrorMessage({ locale,error }: {
  locale: Locale;
  error: unknown;
}) {
  if(!error)
    return null;
  const code=typeof error==='object'&&error!==null&&'code' in error? String(error.code):'';
  const message=/forbidden|permission|viewer|read_only/.test(code)? text(locale,'Tu rol no permite guardar cambios.','Your role cannot save changes.'):/slot|conflict|unavailable/.test(code)? text(locale,'Ese horario ya no está disponible. Actualiza y elige otro.','That time is no longer available. Refresh and choose another.'):/checklist|incomplete/.test(code)? text(locale,'Completa primero los documentos y la lista de revisión.','Complete the documents and checklist first.'):text(locale,'No se pudo completar la acción. Revisa los datos e inténtalo de nuevo.','The action could not be completed. Check the values and try again.');
  return <p role="alert" className="p-error">
    {message}
  </p>
    ;
}
export function Loading({ locale,loading,error,retry }: {
  locale: Locale;
  loading: boolean;
  error: unknown;
  retry: () => void;
}) {
  return <>{loading&&
    <p role="status" className="p-loading">
      {text(locale,'Cargando tus registros…','Loading your records…')}
    </p>
  }
    <ErrorMessage locale={locale} error={error} />
    {!!error&&
      <button className="p-button-secondary" onClick={retry}>
        {text(locale,'Volver a cargar','Reload')}
      </button>
    }</>;
}
export function Recorded({ locale,at,prefix }: {
  locale: Locale;
  at: string;
  prefix?: string;
}) {
  return <p className="p-muted services-source">
    {prefix||text(locale,'Registro local','Local record')} · {dateLabel(at,locale)}
  </p>
    ;
}
export function useAction(locale: Locale,onDone: () => void) {
  const [pending,setPending]=useState(false);
  const [error,setError]=useState<unknown>(null);
  const [success,setSuccess]=useState(false);
  async function run(path: string,method='POST',payload?: unknown) {
    setPending(true);
    setError(null);
    setSuccess(false);
    try {
      await request(path,mutationSchema,{ method,...(payload===undefined? {}:{ body: JSON.stringify(payload) }) });
      setSuccess(true);
      onDone();
      return true;
    }
    catch(e) {
      setError(e);
      return false;
    }
    finally {
      setPending(false);
    }
  }
  return {
    pending,run,feedback: <>
      <ErrorMessage locale={locale} error={error} />
      {success&&
        <p role="status" className="p-success">
          {text(locale,'Cambio guardado en esta demostración.','Change saved in this demonstration.')}
        </p>
      }</>
  };
}
export interface InputSpec {
  name: string;
  es: string;
  en: string;
  type?: string;
  value?: string;
  required?: boolean;
  min?: string;
  max?: string;
  step?: string;
  options?: {
    value: string;
    label: string;
  }[];
  help?: string;
}
export function EditDialog({ locale,title,fields,path,method='POST',extra={},transform,onClose,onSaved,submitLabel }: {
  locale: Locale;
  title: string;
  fields: InputSpec[];
  path: string;
  method?: string;
  extra?: Record<string,unknown>;
  transform?: (values: Record<string,string>) => Record<string,unknown>;
  onClose: () => void;
  onSaved: () => void;
  submitLabel?: string;
}) {
  const [values,setValues]=useState<Record<string,string>>(() => Object.fromEntries(fields.map(f => [f.name,f.value||f.options?.[0]?.value||''])));
  const action=useAction(locale,() => { onSaved(); onClose(); });
  async function submit(event: FormEvent) { event.preventDefault(); await action.run(path,method,{ ...extra,...(transform? transform(values):values) }); }
  return <Modal title={title} onClose={() => {
    if(!action.pending)
      onClose();
  }}>
    <form onSubmit={submit} className="p-stack">
      <div className="p-form-grid">
        {fields.map(f =>
          <Field key={f.name} label={text(locale,f.es,f.en)} help={f.help}>
            {f.options?
              <select value={values[f.name]} onChange={e => setValues({ ...values,[f.name]: e.target.value })} required={f.required!==false}>
                {(values[f.name] && !f.options.some(o => o.value === values[f.name]) ? [{value:values[f.name],label:values[f.name]}, ...f.options] : f.options).map(o =>
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                )}
              </select>
              :
              <input name={f.name} type={f.type||'text'} required={f.required!==false} min={f.min} max={f.max} step={f.step} value={values[f.name]} onChange={e => setValues({ ...values,[f.name]: e.target.value })} />
            }
          </Field>
        )}
      </div>
      {action.feedback}
      <div className="p-actions">
        <button type="button" className="p-button-secondary" disabled={action.pending} onClick={onClose}>
          {text(locale,'Cancelar','Cancel')}
        </button>
        <button className="p-button" disabled={action.pending}>
          {action.pending? text(locale,'Guardando…','Saving…'):submitLabel||text(locale,'Guardar registro','Save record')}
        </button>
      </div>
    </form>
  </Modal>
    ;
}
export function ConfirmDialog({ locale,title,children,path,payload,onClose,onSaved,destructive=false }: {
  locale: Locale;
  title: string;
  children: ReactNode;
  path: string;
  payload?: unknown;
  onClose: () => void;
  onSaved: () => void;
  destructive?: boolean;
}) {
  const action=useAction(locale,() => { onSaved(); onClose(); });
  return <Modal title={title} onClose={() => {
    if(!action.pending)
      onClose();
  }} destructive={destructive}>
    <div className="p-stack">
      {children}{action.feedback}
      <div className="p-actions">
        <button className="p-button-secondary" disabled={action.pending} onClick={onClose}>
          {text(locale,'Volver','Back')}
        </button>
        <button className={destructive? 'p-button-danger':'p-button'} disabled={action.pending} onClick={() => void action.run(path,'POST',payload)}>
          {action.pending? text(locale,'Guardando…','Saving…'):text(locale,'Confirmar en demo','Confirm in demo')}
        </button>
      </div>
    </div>
  </Modal>
    ;
}
export const currencies=['DOP','USD','EUR'].map(value => ({ value,label: value }));
export function DownloadLink({ path,children }: {
  path: string;
  children: ReactNode;
}) {
  return <a className="p-button-secondary" href={`/api/platform${path}`} download>
    {children}
  </a>
    ;
}
