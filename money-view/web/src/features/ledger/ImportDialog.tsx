import { useState, type FormEvent } from "react";
import { z } from "zod";
import { request } from "../../platform/client";
import { Modal, Field, EvidenceLine, Money } from "../../platform/ui";
import type { PlatformPageProps } from "../../platform/types";
import { previewSchema, importSchema, type Account } from "./contracts";
import { copy, categoryLabel } from "./copy";
import { useLedgerMutation, newKey, ledgerError } from "./shared";

export function ImportDialog({
  accounts,
  locale,
  onClose,
  onImported,
}: {
  accounts: Account[];
  onClose: () => void;
  onImported: () => void;
} & PlatformPageProps) {
  const t = copy(locale),
    mutation = useLedgerMutation(locale),
    [accountId, setAccountId] = useState(accounts[0]?.id ?? ""),
    [csv, setCsv] = useState(""),
    [preview, setPreview] = useState<z.infer<typeof previewSchema> | null>(
      null,
    ),
    [receipt, setReceipt] = useState<z.infer<typeof importSchema> | null>(null),
    [idempotencyKey] = useState(newKey);
  function validate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    void mutation.run(async () => {
      setPreview(
        await request("/imports/preview", previewSchema, {
          method: "POST",
          body: JSON.stringify({ account_id: accountId, csv }),
        }),
      );
    });
  }
  async function readFile(file: File | undefined) {
    setPreview(null);
    mutation.setError("");
    if (!file) return;
    if (file.size > 1_000_000) {
      mutation.setError(t.fileTooLarge);
      return;
    }
    try {
      setCsv(await file.text());
    } catch {
      mutation.setError(t.error);
    }
  }
  return (
    <Modal
      title={t.importCsv}
      onClose={() => !mutation.pending && (receipt ? onImported() : onClose())}
    >
      <div className="p-stack">
        {receipt ? (
          <>
            <p className="p-success" role="status">
              {receipt.imported} {t.imported}. {receipt.duplicates}{" "}
              {t.duplicates}.
            </p>
            <EvidenceLine evidence={receipt.source} locale={locale} />
            <button className="p-button" onClick={onImported}>
              {locale === "en" ? "Done" : "Listo"}
            </button>
          </>
        ) : (
          <>
            <p className="p-muted">{t.csvHint}</p>
            <a
              className="p-button-ghost"
              href="/api/platform/transactions/sample.csv"
              download="clara-sample.csv"
            >
              {t.sampleCsv}
            </a>
            <form className="p-stack" onSubmit={validate}>
              <Field label={t.account}>
                <select
                  required
                  value={accountId}
                  onChange={(e) => {
                    setAccountId(e.target.value);
                    setPreview(null);
                  }}
                  disabled={mutation.pending}
                >
                  <option value="" disabled>
                    {t.account}
                  </option>
                  {accounts.map((account) => (
                    <option value={account.id} key={account.id}>
                      {account.name} ({account.currency})
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t.file}>
                <input
                  type="file"
                  accept=".csv,text/csv"
                  disabled={mutation.pending}
                  onChange={(e) => void readFile(e.target.files?.[0])}
                />
              </Field>
              <Field label={t.csvText}>
                <textarea
                  rows={7}
                  className="ledger-csv"
                  required
                  value={csv}
                  maxLength={1_000_000}
                  disabled={mutation.pending}
                  onChange={(e) => {
                    setCsv(e.target.value);
                    setPreview(null);
                  }}
                />
              </Field>
              <button
                className="p-button-secondary"
                disabled={mutation.pending || !accountId}
              >
                {mutation.pending ? t.loading : t.preview}
              </button>
            </form>
            {preview && (
              <section className="p-stack">
                <h3>{t.previewTitle}</h3>
                <p>
                  {preview.valid_count} {t.newRows} · {preview.duplicate_count}{" "}
                  {t.duplicates}
                </p>
                <EvidenceLine evidence={preview.source} locale={locale} />
                {preview.errors.length > 0 && (
                  <div className="p-error" role="alert">
                    <p>{t.csvErrors}</p>
                    <ul>
                      {preview.errors.map((error, index) => (
                        <li key={`${error.line}-${index}`}>
                          {t.line} {error.line}:{" "}
                          {ledgerError(error.code, locale)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="ledger-import-preview">
                  <table className="ledger-table">
                    <thead>
                      <tr>
                        <th>{t.line}</th>
                        <th>{t.merchant}</th>
                        <th>{t.amount}</th>
                        <th>{t.status}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows.slice(0, 50).map((row) => (
                        <tr key={row.line}>
                          <td data-label={t.line}>{row.line}</td>
                          <td data-label={t.merchant}>
                            {row.merchant}
                            <span className="ledger-subline">
                              {row.date} · {categoryLabel(row.category, locale)}
                            </span>
                          </td>
                          <td data-label={t.amount}>
                            <Money
                              amount={row.amount}
                              currency={row.currency}
                              locale={locale}
                            />
                          </td>
                          <td data-label={t.status}>
                            {row.duplicate ? t.duplicate : t.valid}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {preview.rows.length > 50 && (
                  <p className="p-muted">
                    {locale === "en"
                      ? "Showing the first 50 rows. The full file is validated."
                      : "Se muestran las primeras 50 filas. Se valida el archivo completo."}
                  </p>
                )}
                <button
                  className="p-button"
                  disabled={!preview.can_commit || mutation.pending}
                  onClick={() =>
                    void mutation.run(async () =>
                      setReceipt(
                        await request(
                          `/imports/${preview.id}/commit`,
                          importSchema,
                          {
                            method: "POST",
                            body: JSON.stringify({
                              idempotency_key: idempotencyKey,
                            }),
                          },
                        ),
                      ),
                    )
                  }
                >
                  {mutation.pending ? t.saving : t.confirmImport}
                </button>
              </section>
            )}
            {mutation.error && (
              <p className="p-error" role="alert">
                {mutation.error}
              </p>
            )}
            <button
              className="p-button-ghost"
              disabled={mutation.pending}
              onClick={onClose}
            >
              {t.cancel}
            </button>
          </>
        )}
      </div>
    </Modal>
  );
}
