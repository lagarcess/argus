import type { ReactNode } from 'react';
import type { Locale } from '../../platform/types';
import { APIError } from '../../platform/client';
import { planningCopy } from './copy';

export function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

export function formatDate(value: string, locale: Locale): string {
  const parsed = new Date(value.length === 10 ? `${value}T12:00:00Z` : value);
  if (Number.isNaN(parsed.valueOf())) return value;
  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(parsed);
}

export function formatMonth(value: string, locale: Locale): string {
  return formatDate(`${value}-01`, locale);
}

export function errorMessage(error: unknown, locale: Locale): string {
  const copy = planningCopy(locale).errors;
  if (!(error instanceof APIError)) return copy.generic;
  if (error.code === 'network_error') return copy.network;
  if (error.code === 'invalid_response') return copy.invalidResponse;
  if (error.status === 403) return copy.permission;
  if (error.code.includes('currency')) return copy.currencyMismatch;
  if (error.code.includes('allocation') || error.code.includes('overbook')) return copy.overbooked;
  return copy.generic;
}

export function LoadingState({ label }: { label: string }): ReactNode {
  return (
    <div className="p-loading" role="status">
      <span aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function ErrorState({
  message,
  retryLabel,
  onRetry,
}: {
  message: string;
  retryLabel: string;
  onRetry: () => void;
}): ReactNode {
  return (
    <div className="planning-error-state" role="alert">
      <p className="p-error">{message}</p>
      <button className="p-button-secondary" type="button" onClick={onRetry}>
        {retryLabel}
      </button>
    </div>
  );
}

export function InlineError({ children }: { children: ReactNode }): ReactNode {
  return (
    <p className="p-error" role="alert">
      {children}
    </p>
  );
}

export function signedAmountClass(value: string): string {
  return Number(value) < 0 ? 'planning-negative' : '';
}
