import { useEffect, useRef, useState, type ReactNode } from 'react';
import { APIError, request } from '../../platform/client';
import { jsonObjectSchema, type Text } from './contracts';

export function errorText(error: unknown, t: Text) {
  const code = error instanceof APIError ? error.code : '';
  const messages: Record<string, [string, string]> = {
    invalid_credentials: ['La contraseña actual no coincide.', 'The current password does not match.'],
    last_owner_required: ['El hogar necesita otra persona propietaria antes de este cambio.', 'The household needs another owner before this change.'],
    owner_required: ['Solo una persona propietaria puede hacer este cambio.', 'Only an owner can make this change.'],
    confirmation_required: ['Escribe la confirmación exactamente como aparece.', 'Type the confirmation exactly as shown.'],
    invalid_timezone: ['Usa una zona horaria válida, como America/Santo_Domingo.', 'Use a valid time zone, such as America/Santo_Domingo.'],
    validation_error: ['Revisa los campos y vuelve a guardar.', 'Check the fields and save again.'],
    network_error: ['No se pudo conectar. Tus cambios siguen aquí.', 'Could not connect. Your changes are still here.'],
    memory_context_too_large: ['Tus recuerdos superan el espacio disponible. Acorta o elimina alguno y vuelve a guardar.', 'Your memories exceed the available space. Shorten or remove one and save again.'],
    household_export_too_large: ['Este hogar supera el tamaño disponible para una exportación. No se descargó ningún archivo parcial.', 'This household exceeds the supported export size. No partial file was downloaded.'],
  };
  const message = messages[code];
  return message ? t(...message) : t('No se pudo completar la acción. Revisa los datos e inténtalo de nuevo.', 'The action could not be completed. Check the details and try again.');
}

export function useMutation(t: Text, onChanged: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const running = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function run(action: () => Promise<unknown>, success?: () => void) {
    if (running.current) return;
    running.current = true;
    setBusy(true); setError(''); setNotice('');
    try {
      await action();
      onChanged();
      if (mounted.current) { setNotice(t('Cambio guardado.', 'Change saved.')); success?.(); }
    } catch (cause) {
      if (mounted.current) setError(errorText(cause, t));
    } finally {
      running.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return { busy, error, notice, run };
}

export function write(path: string, method: string, body?: unknown) {
  return request(path, jsonObjectSchema, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
}

export function ActionState({ busy, error, notice }: { busy: boolean; error: string; notice: string }) {
  return <>{error && <p className="p-error" role="alert">{error}</p>}{notice && !busy && <p className="p-success" role="status">{notice}</p>}</>;
}

export function LoadState({ loading, error, retry, t }: { loading: boolean; error: Error | null; retry: () => void; t: Text }) {
  return <>{loading && <p className="p-muted" role="status">{t('Cargando…', 'Loading…')}</p>}{error && <div className="p-error" role="alert"><p>{errorText(error, t)}</p><button className="p-button-secondary" onClick={retry}>{t('Reintentar', 'Retry')}</button></div>}</>;
}

export function SaveButton({ busy, t, children }: { busy: boolean; t: Text; children?: ReactNode }) {
  return <button className="p-button" type="submit" disabled={busy}>{busy ? t('Guardando…', 'Saving…') : children ?? t('Guardar cambios', 'Save changes')}</button>;
}

export function Row({ title, value, onClick }: { title: string; value?: string; onClick: () => void }) {
  return <button className="settings-row" onClick={onClick}><span>{title}</span><span className="settings-row-end"><span>{value}</span><span aria-hidden="true">›</span></span></button>;
}
