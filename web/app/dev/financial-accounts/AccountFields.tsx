"use client";

import { useId, type ButtonHTMLAttributes, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { CURRENCY_CODES, currencyName } from "@/lib/home-country";
import { FINANCIAL_ACCOUNT_TYPES } from "@/lib/financial-accounts-api";
import { inlineFailureTextClass } from "@/lib/failure-treatment";
import { ACCOUNT_ERROR_FIELDS, type AccountDraft } from "./account-form-state";

export const inputClass = "min-h-11 w-full rounded-xl border border-black/15 bg-white px-3 py-2 text-base text-black outline-none focus-visible:ring-2 focus-visible:ring-black/35 disabled:opacity-60 dark:border-white/20 dark:bg-[#1b1d20] dark:text-white dark:focus-visible:ring-white/40";

export function AccountButton({ secondary = false, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { secondary?: boolean }) {
  return <button {...props} className={`min-h-11 rounded-full px-5 py-2 text-base font-medium transition-opacity hover:opacity-85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/40 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-45 dark:focus-visible:ring-white/40 dark:focus-visible:ring-offset-[#191c1f] ${secondary ? "bg-black/5 text-black dark:bg-white/10 dark:text-white" : "bg-[#191c1f] text-white dark:bg-white dark:text-[#191c1f]"} ${className}`} />;
}

export function Field({ label, help, error, children }: {
  label: string; help?: string; error?: string; children: (id: string, describedBy?: string) => ReactNode;
}) {
  const id = useId();
  return <div className="space-y-1.5">
    <label htmlFor={id} className="block text-sm font-medium">{label}</label>
    {children(id, error || help ? `${id}-help` : undefined)}
    {error || help ? <p id={`${id}-help`} className={`text-sm leading-relaxed ${error ? inlineFailureTextClass : "text-black/55 dark:text-white/60"}`} role={error ? "alert" : undefined}>{error ?? help}</p> : null}
  </div>;
}

export function AccountFormFields({ draft, setDraft, kind, error, liability = false, hasOpening = false }: {
  draft: AccountDraft;
  setDraft: (draft: AccountDraft) => void;
  kind: "create" | "edit" | "opening";
  error: string | null;
  liability?: boolean;
  hasOpening?: boolean;
}) {
  const { t, i18n } = useTranslation("financial-accounts");
  const update = <K extends keyof AccountDraft>(key: K, value: AccountDraft[K]) => setDraft({ ...draft, [key]: value });
  const fieldError = (field: keyof AccountDraft) => error && ACCOUNT_ERROR_FIELDS[error] === field ? t(`errors.${error}`) : undefined;
  return <div className="space-y-5">
    {kind !== "opening" ? <>
      <Field label={t("fields.type")} error={fieldError("type")}>{(id, describedBy) => <select id={id} aria-describedby={describedBy} className={inputClass} value={draft.type} onChange={(event) => update("type", event.target.value as AccountDraft["type"])}>
        {FINANCIAL_ACCOUNT_TYPES.map((type) => <option key={type} value={type}>{t(`types.${type}`)}</option>)}
      </select>}</Field>
      <Field label={t("fields.currency")} error={fieldError("currency")}>{(id, describedBy) => <select id={id} aria-describedby={describedBy} className={inputClass} value={draft.currency} onChange={(event) => update("currency", event.target.value)}>
        {!CURRENCY_CODES.includes(draft.currency) ? <option value={draft.currency}>{draft.currency}</option> : null}
        {CURRENCY_CODES.map((currency) => <option key={currency} value={currency}>{currency} · {currencyName(currency, i18n.language)}</option>)}
      </select>}</Field>
      <Field label={t("fields.nickname")} error={fieldError("nickname")}>{(id, describedBy) => <input id={id} aria-describedby={describedBy} className={inputClass} value={draft.nickname} autoComplete="off" onChange={(event) => update("nickname", event.target.value)} />}</Field>
    </> : null}
    {kind === "create" || kind === "opening" ? <Field label={t(kind === "create" ? "fields.starting_balance" : liability ? "fields.amount_owed" : "fields.amount")} help={t(kind === "create" ? "help.unknown" : liability ? "help.owed" : "help.amount")} error={fieldError("amount")}>{(id, describedBy) => <input id={id} aria-describedby={describedBy} className={inputClass} value={draft.amount} inputMode="decimal" autoComplete="off" onChange={(event) => update("amount", event.target.value)} />}</Field> : null}
    {kind === "edit" ? <Field label={t("fields.ownership_share")} help={t("help.ownership")} error={fieldError("ownershipShare")}>{(id, describedBy) => <input id={id} aria-describedby={describedBy} className={inputClass} inputMode="decimal" value={draft.ownershipShare} onChange={(event) => update("ownershipShare", event.target.value)} />}</Field> : null}
    {kind === "opening" ? <>
      <Field label={t("fields.date")} help={t("help.date")} error={fieldError("asOf")}>{(id, describedBy) => <input id={id} aria-describedby={describedBy} className={inputClass} value={draft.asOf} placeholder="2026-09-01T09:00:00-04:00" autoComplete="off" spellCheck={false} onChange={(event) => update("asOf", event.target.value)} />}</Field>
      <Field label={t("fields.time_zone")} help={t("help.time_zone")} error={fieldError("timeZone")}>{(id, describedBy) => <input id={id} aria-describedby={describedBy} className={inputClass} value={draft.timeZone} placeholder="America/Santo_Domingo" autoComplete="off" spellCheck={false} onChange={(event) => update("timeZone", event.target.value)} />}</Field>
      {hasOpening ? <Field label={t("fields.reason")} error={fieldError("reason")}>{(id, describedBy) => <textarea id={id} aria-describedby={describedBy} className={`${inputClass} min-h-24`} value={draft.reason} onChange={(event) => update("reason", event.target.value)} />}</Field> : null}
    </> : null}
  </div>;
}
