"use client";

import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import AdaptivePanel from "@/components/ui/AdaptivePanel";
import { randomId } from "@/lib/random-id";
import { useBusiness } from "./BusinessWorkspace";
import { RECEIPT_CATEGORY_IDS } from "./business-format";
import { primaryButtonClass, secondaryButtonClass, useCategoryLabel } from "./business-ui";

const inputClass =
  "mt-1.5 block min-h-11 w-full rounded-[12px] border border-black/10 bg-white px-3 text-[16px] text-black outline-none focus-visible:border-black/30 focus-visible:ring-[0.125rem] focus-visible:ring-black/10 dark:border-white/10 dark:bg-[#141517] dark:text-white";

function today(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

export default function RecordExpenseDialog({
  isOpen,
  onClose,
  onRecorded,
}: {
  isOpen: boolean;
  onClose: () => void;
  onRecorded: () => void;
}) {
  if (!isOpen) return null;
  return <RecordExpenseSurface onClose={onClose} onRecorded={onRecorded} />;
}

function RecordExpenseSurface({ onClose, onRecorded }: { onClose: () => void; onRecorded: () => void }) {
  const { t } = useTranslation();
  const categoryLabel = useCategoryLabel();
  const { source, records } = useBusiness();
  const accounts = records.workspace?.accounts ?? [];
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [occurredOn, setOccurredOn] = useState(today);
  const [categoryId, setCategoryId] = useState("");
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [state, setState] = useState<"idle" | "saving" | "failed">("idle");
  const key = useRef(randomId());
  const account = accounts.find((item) => item.id === accountId);
  const valid = Boolean(accountId && /^\d+(\.\d{1,2})?$/.test(amount.trim()) && Number(amount) > 0 && occurredOn);

  const save = async () => {
    if (!valid) return;
    setState("saving");
    try {
      await source.recordExpense(
        {
          account_id: accountId,
          amount: amount.trim(),
          occurred_on: occurredOn,
          merchant: merchant.trim() || null,
          category_id: categoryId || null,
        },
        key.current,
      );
      onRecorded();
    } catch {
      setState("failed");
    }
  };

  return (
    <AdaptivePanel
      title={t("business.actions.record_expense", "Record expense")}
      closeLabel={t("common.close", "Close")}
      onClose={onClose}
      width="md"
      footer={
        <div className="flex justify-end gap-2 px-4 pb-4">
          <button type="button" className={secondaryButtonClass} onClick={onClose}>
            {t("common.cancel", "Cancel")}
          </button>
          <button type="button" className={primaryButtonClass} disabled={!valid || state === "saving"} onClick={() => void save()}>
            {state === "saving" ? t("business.review.confirming", "Saving…") : t("business.record.save", "Save expense")}
          </button>
        </div>
      }
    >
      <div className="space-y-4 px-4 pb-2">
        {accounts.length === 0 ? (
          <p className="text-[14px] text-black/65 dark:text-white/65">
            {t("business.record.no_accounts", "Add a business account first so we know where this expense was paid from.")}
          </p>
        ) : null}
        <label className="block text-[13px] font-medium text-black/60 dark:text-white/60">
          {t("business.review.merchant", "Merchant")}
          <input className={inputClass} value={merchant} onChange={(event) => setMerchant(event.target.value)} autoComplete="off" />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-[13px] font-medium text-black/60 dark:text-white/60">
            {account
              ? t("business.record.amount_in", "Total in {{currency}}", { currency: account.currency })
              : t("business.review.amount", "Total")}
            <input inputMode="decimal" className={`${inputClass} tabular-nums`} value={amount} onChange={(event) => setAmount(event.target.value)} />
          </label>
          <label className="block text-[13px] font-medium text-black/60 dark:text-white/60">
            {t("business.review.date", "Date")}
            <input type="date" className={inputClass} value={occurredOn} onChange={(event) => setOccurredOn(event.target.value)} />
          </label>
        </div>
        <label className="block text-[13px] font-medium text-black/60 dark:text-white/60">
          {t("business.review.account", "Paid from")}
          <select className={inputClass} value={accountId} onChange={(event) => setAccountId(event.target.value)}>
            {accounts.map((item) => (
              <option key={item.id} value={item.id}>{`${item.nickname ?? item.type} · ${item.currency}`}</option>
            ))}
          </select>
        </label>
        <label className="block text-[13px] font-medium text-black/60 dark:text-white/60">
          {t("business.review.category", "Category")}
          <select className={inputClass} value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
            <option value="">{categoryLabel(null)}</option>
            {RECEIPT_CATEGORY_IDS.map((id) => (
              <option key={id} value={id}>{categoryLabel(id)}</option>
            ))}
          </select>
        </label>
        {state === "failed" ? (
          <p role="alert" className="text-[14px] text-[#a8434c] dark:text-[#ec9aa0]">
            {t("business.record.failed", "We couldn't save this expense. Try again. It won't be saved twice.")}
          </p>
        ) : null}
      </div>
    </AdaptivePanel>
  );
}
