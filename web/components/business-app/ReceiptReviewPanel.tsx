"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, ArrowLeft, Download, RotateCcw } from "lucide-react";
import { useTranslation } from "react-i18next";
import MoneyInput from "@/components/money/MoneyInput";
import { moneyProblemFromServer } from "@/lib/money-entry";
import { randomId } from "@/lib/random-id";
import type { ReceiptDetail, ReceiptReviewFields } from "@/lib/business-api";
import { useBusiness } from "./BusinessWorkspace";
import { formatDay, formatMoney, RECEIPT_CATEGORY_IDS } from "./business-format";
import {
  cardClass,
  LoadingRows,
  primaryButtonClass,
  secondaryButtonClass,
  StatusPill,
  useAttentionLabel,
  useCategoryLabel,
} from "./business-ui";

type Draft = Record<keyof ReceiptReviewFields, string>;

const FIELDS: (keyof ReceiptReviewFields)[] = [
  "merchant",
  "occurred_on",
  "amount",
  "currency",
  "category_id",
  "account_id",
];

function draftFrom(detail: ReceiptDetail): Draft {
  return Object.fromEntries(FIELDS.map((key) => [key, detail[key] ?? ""])) as Draft;
}

const inputClass =
  "mt-1.5 block min-h-11 w-full rounded-[12px] border border-black/10 bg-white px-3 text-[16px] text-black outline-none transition-colors focus-visible:border-black/30 focus-visible:ring-[0.125rem] focus-visible:ring-black/10 disabled:bg-black/[0.03] disabled:text-black/50 dark:border-white/10 dark:bg-[#141517] dark:text-white dark:disabled:bg-white/[0.03]";

function SourcePreview({ detail }: { detail: ReceiptDetail }) {
  const { t } = useTranslation();
  const { source } = useBusiness();
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  // A data URL, because the app's image policy allows `data:` and not `blob:`.
  useEffect(() => {
    let cancelled = false;
    source
      .receiptSource(detail.id)
      .then(
        (blob) =>
          new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result));
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(blob);
          }),
      )
      .then((dataUrl) => !cancelled && setUrl(dataUrl))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [detail.id, source]);

  const isPdf = detail.media_type === "application/pdf";
  return (
    <figure className={`${cardClass} flex flex-col p-3`}>
      <div className="flex min-h-[200px] flex-1 items-center justify-center overflow-hidden rounded-[14px] bg-black/[0.03] dark:bg-white/[0.04] desktop:min-h-[280px]">
        {failed ? (
          <p className="px-6 text-center text-[14px] text-black/55 dark:text-white/55">
            {t("business.review.source_error", "We couldn't open the original receipt. It is still stored.")}
          </p>
        ) : !url ? (
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-black/15 border-t-black/50" aria-label={t("common.loading", "Loading")} />
        ) : isPdf && source.mode === "live" ? (
          <iframe title={t("business.review.source", "Original receipt")} src={url} className="h-[480px] w-full" />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={t("business.review.source", "Original receipt")} className="max-h-[300px] w-auto object-contain desktop:max-h-[520px]" />
        )}
      </div>
      <figcaption className="mt-3 flex items-center justify-between gap-2 px-1 text-[13px] text-black/55 dark:text-white/55">
        <span className="truncate">{detail.filename ?? t("business.review.source", "Original receipt")}</span>
        {url ? (
          <a href={url} download={detail.filename ?? "receipt"} className="flex min-h-11 items-center gap-1.5 rounded-full px-3 font-medium hover:bg-black/5 dark:hover:bg-white/5">
            <Download className="h-4 w-4" />
            {t("business.review.download", "Download")}
          </a>
        ) : null}
      </figcaption>
    </figure>
  );
}

export default function ReceiptReviewPanel({ receiptId }: { receiptId: string }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? "en";
  const categoryLabel = useCategoryLabel();
  const attentionLabel = useAttentionLabel();
  const { source, records, reload, openPanel } = useBusiness();
  const [detail, setDetail] = useState<ReceiptDetail | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<"prepare" | "confirm" | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [amountInvalid, setAmountInvalid] = useState(false);
  const [amountError, setAmountError] = useState<string | null>(null);
  // One key per receipt version, so a retry of the same confirm replays it and
  // a confirm of a newer version is a new request.
  const confirmKey = useRef<{ version: number; key: string } | null>(null);
  const confirmKeyFor = (version: number) => {
    if (confirmKey.current?.version !== version) confirmKey.current = { version, key: randomId() };
    return confirmKey.current.key;
  };

  useEffect(() => {
    let cancelled = false;
    source
      .receipt(receiptId)
      .then((next) => {
        if (cancelled) return;
        setDetail(next);
        setDraft(draftFrom(next));
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [receiptId, source]);

  const accounts = records.workspace?.accounts ?? [];
  const currencies = records.workspace?.currencies ?? [];
  const missing = useMemo(
    () => (detail && draft ? detail.missing_fields.filter((key) => !draft[key]?.trim()) : []),
    [detail, draft],
  );
  const confirmed = detail?.status === "confirmed";
  const waitingForAi = detail?.status === "queued" || detail?.status === "preparing";

  if (failed) {
    return (
      <p role="alert" className="text-[14px] text-black/70 dark:text-white/70">
        {t("business.review.error", "This receipt isn't available. It may have been removed.")}
      </p>
    );
  }
  if (!detail || !draft) return <LoadingRows rows={4} />;
  // A receipt with no purchase yet opens for entry only when the backend says so.
  const locked = confirmed || (detail.version === 0 && !detail.enterable);

  const changedFields = (): Partial<ReceiptReviewFields> =>
    Object.fromEntries(
      FIELDS.filter((key) => (detail[key] ?? "") !== draft[key]).map((key) => [key, draft[key] || null]),
    );

  const show = (next: ReceiptDetail) => {
    setDetail(next);
    setDraft(draftFrom(next));
    setAmountInvalid(false);
  };

  const confirmProblem = (code: string | undefined, current: Draft) => {
    if (code === "stale_version") {
      return t("business.review.stale", "This receipt changed since you opened it. Review the current details before confirming.");
    }
    const account = accounts.find((item) => item.id === current.account_id);
    if (code === "currency_mismatch" && account) {
      return t("business.review.currency_mismatch", "This account uses {{account}}. Choose an account in {{receipt}} or correct the currency.", {
        account: account.currency,
        receipt: current.currency,
      });
    }
    if (code === "missing_fields") {
      return t("business.review.missing", "Fill in the details marked Needed to save this expense.");
    }
    return t("business.review.confirm_failed", "We couldn't confirm this expense. Nothing was saved twice. Try again.");
  };

  const prepare = async () => {
    setBusy("prepare");
    setProblem(null);
    try {
      await source.prepareReceipt(detail.id);
      show(await source.receipt(detail.id));
      reload();
    } catch {
      setProblem(t("business.review.prepare_failed", "We couldn't start preparation. Your receipt is saved. Try again."));
    } finally {
      setBusy(null);
    }
  };

  const confirm = async () => {
    setBusy("confirm");
    setProblem(null);
    const submitted = draft;
    try {
      const changes = changedFields();
      let reviewed = detail;
      if (Object.keys(changes).length) {
        reviewed = await source.saveReview(detail.id, detail.version, changes);
        show(reviewed);
      }
      show(await source.confirmReceipt(reviewed.id, reviewed.version, confirmKeyFor(reviewed.version)));
      reload();
    } catch (error) {
      const code = (error as { code?: string }).code;
      if (moneyProblemFromServer(code, submitted.currency)) setAmountError(code ?? null);
      else setProblem(confirmProblem(code, submitted));
      if (code === "stale_version") {
        const fresh = await source.receipt(detail.id).catch(() => null);
        if (fresh) show(fresh);
      }
    } finally {
      setBusy(null);
    }
  };

  const field = (key: keyof ReceiptReviewFields, label: string, control: React.ReactNode) => (
    <label className="block">
      <span className="flex items-center justify-between text-[13px] font-medium text-black/60 dark:text-white/60">
        {label}
        {!confirmed && missing.includes(key) ? (
          <span className="text-[12px] font-normal text-[#a8434c] dark:text-[#ec9aa0]">
            {t("business.review.needed", "Needed")}
          </span>
        ) : null}
      </span>
      {control}
    </label>
  );
  const set = (key: keyof ReceiptReviewFields) => (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setDraft((current) => (current ? { ...current, [key]: event.target.value } : current));

  return (
    <section aria-labelledby="receipt-review-title">
      <button
        type="button"
        onClick={() => openPanel({ kind: confirmed ? "expenses" : "inbox" })}
        className="mb-4 flex min-h-11 items-center gap-1.5 rounded-full pr-3 text-[14px] font-medium text-black/60 hover:text-black dark:text-white/60 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        {confirmed ? t("business.nav.expenses", "Expenses") : t("business.nav.inbox", "Inbox")}
      </button>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <h2 id="receipt-review-title" className="font-display text-[24px] font-medium tracking-tight text-black dark:text-white">
          {confirmed ? t("business.review.saved_title", "Saved expense") : t("business.review.title", "Review receipt")}
        </h2>
        <StatusPill status={detail.status} />
      </div>

      <div className="grid gap-4 desktop:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <SourcePreview detail={detail} />

        <div className="space-y-4">
          {detail.status === "needs_attention" ? (
            <div role="alert" data-testid="receipt-attention" className={`${cardClass} text-[14px] text-black/75 dark:text-white/75`}>
              <p className="flex gap-2.5">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#d66d75]" aria-hidden="true" />
                <span>{attentionLabel(detail.attention)}</span>
              </p>
              {detail.preparable ? (
                <>
                  <p className="mt-3 text-[13px] text-black/55 dark:text-white/55">
                    {t("business.review.retry_consent", "Trying again sends this receipt to our AI provider.")}
                  </p>
                  <button type="button" disabled={busy !== null} onClick={() => void prepare()} className={`${secondaryButtonClass} mt-3`}>
                    <RotateCcw className="h-4 w-4" aria-hidden="true" />
                    {t("business.review.retry", "Try again with AI")}
                  </button>
                </>
              ) : null}
            </div>
          ) : detail.preparable ? (
            <div className={cardClass}>
              <p className="text-[14px] text-black/75 dark:text-white/75">
                {t("business.review.consent", "Cuadrao can read this receipt with AI and fill in the details for you to check. The receipt is sent to our AI provider only if you choose this. You can also fill in the details yourself.")}
              </p>
              <button type="button" disabled={busy !== null} onClick={() => void prepare()} className={`${secondaryButtonClass} mt-3`}>
                {t("business.review.prepare", "Prepare with AI")}
              </button>
            </div>
          ) : null}
          {waitingForAi ? (
            <div role="status" className={`${cardClass} text-[14px] text-black/70 dark:text-white/70`}>
              {t("business.review.preparing", "Reading your receipt. You can leave this page; the result will wait in your inbox.")}
            </div>
          ) : null}

          <div className={`${cardClass} space-y-4`}>
            {field(
              "merchant",
              t("business.review.merchant", "Merchant"),
              <input className={inputClass} value={draft.merchant} onChange={set("merchant")} disabled={locked} autoComplete="off" />,
            )}
            <div className="grid grid-cols-2 gap-3">
              {field(
                "occurred_on",
                t("business.review.date", "Date"),
                <input type="date" className={inputClass} value={draft.occurred_on} onChange={set("occurred_on")} disabled={locked} />,
              )}
              {field(
                "category_id",
                t("business.review.category", "Category"),
                <select className={inputClass} value={draft.category_id} onChange={set("category_id")} disabled={locked}>
                  <option value="">{categoryLabel(null)}</option>
                  {RECEIPT_CATEGORY_IDS.map((id) => (
                    <option key={id} value={id}>
                      {categoryLabel(id)}
                    </option>
                  ))}
                </select>,
              )}
            </div>
            <div className="grid grid-cols-[minmax(0,1fr)_7.5rem] items-start gap-3">
              {field(
                "amount",
                t("business.review.amount", "Total"),
                <MoneyInput
                  label={t("business.review.amount", "Total")}
                  currency={draft.currency}
                  value={draft.amount || null}
                  onValueChange={({ value, invalid }) => {
                    setDraft((current) => (current ? { ...current, amount: value ?? "" } : current));
                    setAmountInvalid(invalid);
                    setAmountError(null);
                  }}
                  serverError={amountError}
                  description={!confirmed && missing.includes("amount") ? t("business.review.needed", "Needed") : null}
                  disabled={locked}
                  testId="receipt-review-amount"
                />,
              )}
              {field(
                "currency",
                t("business.review.currency", "Currency"),
                <select className={inputClass} value={draft.currency} onChange={set("currency")} disabled={locked}>
                  <option value="">{t("business.review.choose", "Choose")}</option>
                  {currencies.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>,
              )}
            </div>
            {field(
              "account_id",
              t("business.review.account", "Paid from"),
              <select className={inputClass} value={draft.account_id} onChange={set("account_id")} disabled={locked}>
                <option value="">{t("business.review.choose_account", "Choose an account")}</option>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {`${account.nickname ?? account.type} · ${account.currency}`}
                  </option>
                ))}
              </select>,
            )}
          </div>

          {detail.evidence ? (
            <details className={cardClass}>
              <summary className="cursor-pointer text-[14px] font-medium text-black/70 dark:text-white/70">
                {t("business.review.evidence", "What the receipt says")}
              </summary>
              <dl className="mt-3 space-y-1.5 text-[13px] text-black/65 dark:text-white/65">
                {detail.evidence.merchant ? <div className="flex justify-between gap-3"><dt>{t("business.review.merchant", "Merchant")}</dt><dd className="text-right">{detail.evidence.merchant}</dd></div> : null}
                {detail.evidence.occurred_on ? <div className="flex justify-between gap-3"><dt>{t("business.review.date", "Date")}</dt><dd>{formatDay(detail.evidence.occurred_on, locale)}</dd></div> : null}
                {detail.evidence.lines.map((line, index) => (
                  <div key={index} className="flex justify-between gap-3"><dt className="truncate">{line.description}</dt><dd className="tabular-nums">{formatMoney(line.amount, detail.evidence?.currency ?? null, locale)}</dd></div>
                ))}
                {detail.evidence.tax ? <div className="flex justify-between gap-3"><dt>{t("business.review.tax", "Tax")}</dt><dd className="tabular-nums">{formatMoney(detail.evidence.tax, detail.evidence.currency, locale)}</dd></div> : null}
                {detail.evidence.total ? <div className="flex justify-between gap-3 font-medium text-black dark:text-white"><dt>{t("business.review.amount", "Total")}</dt><dd className="tabular-nums">{formatMoney(detail.evidence.total, detail.evidence.currency, locale)}</dd></div> : null}
              </dl>
              <p className="mt-3 text-[12px] text-black/45 dark:text-white/45">
                {t("business.review.evidence_note", "Your corrections don't change what was read from the receipt. One receipt saves one expense for its total.")}
              </p>
            </details>
          ) : null}

          {problem ? (
            <p role="alert" className="text-[14px] text-[#a8434c] dark:text-[#ec9aa0]">{problem}</p>
          ) : null}

          {confirmed ? (
            <div className={`${cardClass} flex flex-wrap items-center justify-between gap-3`}>
              <p className="text-[14px] text-black/75 dark:text-white/75">
                {t("business.review.saved_body", "Saved as one expense of {{amount}}.", { amount: formatMoney(detail.amount, detail.currency, locale) })}
              </p>
              <button type="button" className={secondaryButtonClass} onClick={() => openPanel({ kind: "expenses" })}>
                {t("business.review.view_expenses", "View expenses")}
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                className={primaryButtonClass}
                disabled={busy !== null || missing.length > 0 || amountInvalid || waitingForAi || locked}
                onClick={() => void confirm()}
              >
                {busy === "confirm" ? t("business.review.confirming", "Saving…") : t("business.review.confirm", "Confirm expense")}
              </button>
              {missing.length > 0 ? (
                <span className="text-[13px] text-black/55 dark:text-white/55">
                  {t("business.review.missing", "Fill in the details marked Needed to save this expense.")}
                </span>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
