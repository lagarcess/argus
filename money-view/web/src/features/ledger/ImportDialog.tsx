import { useEffect, useRef, useState, type FormEvent } from "react";
import { z } from "zod";
import { APIError, request } from "../../platform/client";
import { Modal, Field, EvidenceLine, Money } from "../../platform/ui";
import type { PlatformPageProps } from "../../platform/types";
import {
  importInspectionSchema,
  previewSchema,
  importSchema,
  type Account,
} from "./contracts";
import { copy, categoryLabel, statementCopy, statementError } from "./copy";
import { newKey, ledgerError } from "./shared";

type Mapping = Record<
  | "date"
  | "merchant"
  | "description"
  | "amount"
  | "debit"
  | "credit"
  | "currency"
  | "source_id"
  | "kind"
  | "category",
  string
>;
const emptyMapping: Mapping = {
  date: "",
  merchant: "",
  description: "",
  amount: "",
  debit: "",
  credit: "",
  currency: "",
  source_id: "",
  kind: "",
  category: "",
};

export function ImportDialog({
  accounts,
  locale,
  currency,
  query,
  onClose,
  onImported,
}: {
  accounts: Account[];
  onClose: () => void;
  onImported: () => void;
} & PlatformPageProps) {
  const t = copy(locale),
    s = statementCopy(locale);
  const [accountId, setAccountId] = useState(
      () =>
        accounts.find(
          (account) =>
            account.id === query.get("account_id") && !account.deleted_at,
        )?.id ??
        accounts.find(
          (account) => account.currency === currency && !account.deleted_at,
        )?.id ??
        "",
    ),
    [csv, setCsv] = useState(""),
    [fileName, setFileName] = useState("");
  const [delimiter, setDelimiter] = useState(","),
    [headerRow, setHeaderRow] = useState(1),
    [dateFormat, setDateFormat] = useState("YMD"),
    [decimal, setDecimal] = useState("."),
    [positiveKind, setPositiveKind] = useState("");
  const [layout, setLayout] = useState("signed"),
    [mapping, setMapping] = useState<Mapping>(emptyMapping);
  const [inspection, setInspection] = useState<z.infer<
      typeof importInspectionSchema
    > | null>(null),
    [preview, setPreview] = useState<z.infer<typeof previewSchema> | null>(
      null,
    ),
    [receipt, setReceipt] = useState<z.infer<typeof importSchema> | null>(null);
  const [decisions, setDecisions] = useState<Record<number, "import" | "skip">>(
      {},
    ),
    [reviewPage, setReviewPage] = useState(0);
  const [pending, setPending] = useState(false),
    [reading, setReading] = useState(false),
    [error, setError] = useState("");
  const fileEpoch = useRef(0),
    requestEpoch = useRef(0),
    controller = useRef<AbortController | null>(null),
    key = useRef(newKey());
  useEffect(
    () => () => {
      fileEpoch.current++;
      requestEpoch.current++;
      controller.current?.abort();
    },
    [],
  );
  function cancelWork() {
    fileEpoch.current++;
    requestEpoch.current++;
    controller.current?.abort();
    setPending(false);
    setReading(false);
  }
  function close() {
    if (pending) return;
    cancelWork();
    if (receipt) onImported();
    else onClose();
  }
  function invalidate() {
    setPreview(null);
    setInspection(null);
    setDecisions({});
    setError("");
  }
  async function run(action: (signal: AbortSignal) => Promise<void>) {
    const epoch = ++requestEpoch.current;
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setPending(true);
    setError("");
    try {
      await action(abort.signal);
    } catch (caught) {
      if (epoch === requestEpoch.current && !abort.signal.aborted) {
        const code = caught instanceof APIError ? caught.code : "unknown";
        setError(statementError(code, locale) ?? ledgerError(code, locale));
      }
    } finally {
      if (epoch === requestEpoch.current) setPending(false);
    }
  }
  async function readFile(file: File | undefined) {
    const epoch = ++fileEpoch.current;
    setCsv("");
    setFileName("");
    invalidate();
    setReading(false);
    if (!file) return;
    if (!/\.(csv|tsv)$/i.test(file.name)) {
      setError(s.supported);
      return;
    }
    if (file.size > 1_000_000) {
      setError(t.fileTooLarge);
      return;
    }
    setReading(true);
    try {
      const bytes = await file.arrayBuffer();
      if (epoch !== fileEpoch.current) return;
      const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      setCsv(text);
      setFileName(file.name);
      setDelimiter(file.name.toLowerCase().endsWith(".tsv") ? "\t" : ",");
    } catch {
      if (epoch === fileEpoch.current) setError(s.invalidFile);
    } finally {
      if (epoch === fileEpoch.current) setReading(false);
    }
  }
  const basePayload = () => ({
    account_id: accountId,
    csv,
    mode: "statement",
    delimiter,
    header_row: headerRow,
    date_format: dateFormat,
    decimal_separator: decimal,
    positive_kind: positiveKind || null,
    file_name: fileName || null,
  });
  function inspect(e: FormEvent) {
    e.preventDefault();
    if (!csv) {
      setError(s.noFile);
      return;
    }
    void run(async (signal) => {
      const result = await request("/imports/preview", importInspectionSchema, {
        method: "POST",
        signal,
        body: JSON.stringify(basePayload()),
      });
      if (signal.aborted) return;
      setInspection(result);
      setMapping(
        Object.fromEntries(
          Object.keys(emptyMapping).map((field) => [
            field,
            result.headers.includes(field) ? field : "",
          ]),
        ) as Mapping,
      );
    });
  }
  function prepare(e: FormEvent) {
    e.preventDefault();
    const chosen = {
      ...mapping,
      amount: layout === "signed" ? mapping.amount : "",
      debit: layout === "separate" ? mapping.debit : "",
      credit: layout === "separate" ? mapping.credit : "",
    };
    void run(async (signal) => {
      const result = await request("/imports/preview", previewSchema, {
        method: "POST",
        signal,
        body: JSON.stringify({
          ...basePayload(),
          mapping: Object.fromEntries(
            Object.entries(chosen).map(([field, column]) => [
              field,
              column || null,
            ]),
          ),
        }),
      });
      if (signal.aborted) return;
      setPreview(result);
      setDecisions({});
      setReviewPage(0);
      key.current = newKey();
    });
  }
  function commit() {
    if (!preview) return;
    void run(async (signal) => {
      const result = await request(
        `/imports/${preview.id}/commit`,
        importSchema,
        {
          method: "POST",
          signal,
          body: JSON.stringify({
            idempotency_key: key.current,
            preview_digest: preview.preview_digest,
            decisions: Object.entries(decisions).map(([line, action]) => ({
              line: Number(line),
              action,
            })),
          }),
        },
      );
      if (!signal.aborted) setReceipt(result);
    });
  }
  function column(
    field: keyof Mapping,
    label: string,
    required = false,
    help?: string,
  ) {
    const example =
      inspection?.sample_rows[0]?.[inspection.headers.indexOf(mapping[field])];
    const fieldHelp = [
      help,
      example ? `${locale === "en" ? "Example" : "Ejemplo"}: ${example}` : "",
    ]
      .filter(Boolean)
      .join(" ");
    return (
      <Field label={label} help={fieldHelp}>
        <select
          value={mapping[field]}
          required={required}
          disabled={pending}
          onChange={(e) =>
            setMapping((current) => ({ ...current, [field]: e.target.value }))
          }
        >
          <option value="">{required ? s.choose : s.notIncluded}</option>
          {inspection?.headers.map((header) => (
            <option key={header} value={header}>
              {header}
            </option>
          ))}
        </select>
      </Field>
    );
  }
  const possible =
      preview?.rows.filter((row) => row.duplicate_status === "possible") ?? [],
    remaining = possible.filter((row) => !decisions[row.line]).length;
  return (
    <Modal title={s.title} onClose={close}>
      <div className="p-stack">
        {receipt ? (
          <>
            <p role="status" className="p-success">
              {receipt.imported} {s.imported}. {receipt.duplicates}{" "}
              {t.duplicates}.
            </p>
            <EvidenceLine evidence={receipt.source} locale={locale} />
            <button className="p-button" onClick={onImported}>
              {s.done}
            </button>
          </>
        ) : preview ? (
          <>
            <h3>{s.reviewStep}</h3>
            <p>
              {preview.valid_count} {t.newRows} · {preview.duplicate_count}{" "}
              {s.exact.toLowerCase()}
            </p>
            <EvidenceLine evidence={preview.source} locale={locale} />
            {preview.errors.length > 0 && (
              <div className="p-error" role="alert">
                <p>{t.csvErrors}</p>
                <ul>
                  {preview.errors.map((item, index) => (
                    <li key={`${item.line}-${index}`}>
                      {t.line} {item.line}:{" "}
                      {statementError(item.code, locale) ??
                        ledgerError(item.code, locale)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {possible.length > 0 && (
              <section className="p-stack">
                <p>{s.reviewHelp}</p>
                <div className="p-actions">
                  <button
                    className="p-button-secondary"
                    disabled={pending}
                    onClick={() =>
                      setDecisions(
                        Object.fromEntries(
                          possible.map((row) => [row.line, "import" as const]),
                        ),
                      )
                    }
                  >
                    {s.keepAll}
                  </button>
                  <button
                    className="p-button-secondary"
                    disabled={pending}
                    onClick={() =>
                      setDecisions(
                        Object.fromEntries(
                          possible.map((row) => [row.line, "skip" as const]),
                        ),
                      )
                    }
                  >
                    {s.skipAll}
                  </button>
                </div>
                <p role="status">
                  {remaining} {s.reviewRemaining}
                </p>
              </section>
            )}
            {!preview.rows.length ? (
              <p>{s.empty}</p>
            ) : (
              <>
                <div className="ledger-import-preview">
                  <table className="ledger-table">
                    <thead>
                      <tr>
                        <th>{t.date}</th>
                        <th>{t.merchant}</th>
                        <th>{t.amount}</th>
                        <th>{s.decision}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.rows
                        .slice(reviewPage * 25, (reviewPage + 1) * 25)
                        .map((row) => (
                          <tr key={row.line}>
                            <td data-label={t.date}>
                              {row.date}
                              <span className="ledger-subline">
                                {t.line} {row.line}
                              </span>
                            </td>
                            <td data-label={t.merchant}>
                              {row.merchant}
                              <span className="ledger-subline">
                                {row.description}
                              </span>
                              <span className="ledger-subline">
                                {categoryLabel(row.kind, locale)} ·{" "}
                                {categoryLabel(row.category, locale)}
                              </span>
                            </td>
                            <td data-label={t.amount}>
                              <Money
                                amount={row.amount}
                                currency={row.currency}
                                locale={locale}
                              />
                            </td>
                            <td data-label={s.decision}>
                              {row.duplicate_status === "possible" ? (
                                <Field
                                  label={`${s.possible}, ${t.line} ${row.line}`}
                                >
                                  <select
                                    value={decisions[row.line] ?? ""}
                                    disabled={pending}
                                    onChange={(e) =>
                                      setDecisions((current) => {
                                        const next = { ...current };
                                        if (e.target.value)
                                          next[row.line] = e.target.value as
                                            "import" | "skip";
                                        else delete next[row.line];
                                        return next;
                                      })
                                    }
                                  >
                                    <option value="">{s.undecided}</option>
                                    <option value="import">{s.keep}</option>
                                    <option value="skip">{s.skip}</option>
                                  </select>
                                </Field>
                              ) : row.duplicate ? (
                                s.exact
                              ) : (
                                s.newRow
                              )}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
                <div className="p-pagination">
                  <button
                    className="p-button-ghost"
                    disabled={reviewPage === 0}
                    onClick={() => setReviewPage((page) => page - 1)}
                  >
                    {t.previous}
                  </button>
                  <span>
                    {reviewPage + 1} {t.of}{" "}
                    {Math.ceil(preview.rows.length / 25)}
                  </span>
                  <button
                    className="p-button-ghost"
                    disabled={(reviewPage + 1) * 25 >= preview.rows.length}
                    onClick={() => setReviewPage((page) => page + 1)}
                  >
                    {t.next}
                  </button>
                </div>
              </>
            )}
            {preview.expires_at && (
              <p className="p-muted">
                {s.expired}{" "}
                {new Intl.DateTimeFormat(locale, {
                  hour: "numeric",
                  minute: "2-digit",
                }).format(new Date(preview.expires_at))}
                .
              </p>
            )}
            <div className="p-actions">
              <button
                className="p-button-secondary"
                disabled={pending}
                onClick={() => {
                  setPreview(null);
                  setError("");
                }}
              >
                {s.back}
              </button>
              <button
                className="p-button"
                disabled={pending || !preview.can_commit || remaining > 0}
                onClick={commit}
              >
                {pending ? t.saving : s.confirm}
              </button>
            </div>
          </>
        ) : inspection ? (
          <form className="p-stack" onSubmit={prepare}>
            <h3>{s.mappingStep}</h3>
            <p className="p-muted">{s.mapIntro}</p>
            <span className="p-badge">
              {accounts.find((account) => account.id === accountId)?.name} ·{" "}
              {inspection.currency}
            </span>
            <div className="p-form-grid">
              {column("date", t.date, true)}
              {column("merchant", t.merchant, true)}
              <Field label={s.dateFormat}>
                <select
                  value={dateFormat}
                  disabled={pending}
                  onChange={(e) => setDateFormat(e.target.value)}
                >
                  <option value="YMD">{s.ymd}</option>
                  <option value="DMY">{s.dmy}</option>
                  <option value="MDY">{s.mdy}</option>
                </select>
              </Field>
              <Field label={s.decimal} help={s.decimalHelp}>
                <select
                  value={decimal}
                  disabled={pending}
                  onChange={(e) => setDecimal(e.target.value)}
                >
                  <option value=".">{s.dotDecimal}</option>
                  <option value=",">{s.commaDecimal}</option>
                </select>
              </Field>
            </div>
            <Field label={s.amountLayout}>
              <select
                value={layout}
                disabled={pending}
                onChange={(e) => setLayout(e.target.value)}
              >
                <option value="signed">{s.signed}</option>
                <option value="separate">{s.separate}</option>
              </select>
            </Field>
            {layout === "signed" ? (
              column("amount", t.amount, true)
            ) : (
              <div className="p-form-grid">
                {column("debit", s.debit, !mapping.credit)}
                {column("credit", s.credit, !mapping.debit)}
              </div>
            )}
            {column("source_id", s.sourceId, false, s.sourceHelp)}
            <Field label={s.positiveKind} help={s.positiveHelp}>
              <select
                value={positiveKind}
                disabled={pending}
                onChange={(e) => setPositiveKind(e.target.value)}
              >
                <option value="">{s.chooseKind}</option>
                {["income", "refund", "adjustment"].map((kind) => (
                  <option key={kind} value={kind}>
                    {categoryLabel(kind, locale)}
                  </option>
                ))}
              </select>
            </Field>
            <details>
              <summary>{s.optional}</summary>
              <div className="p-form-grid">
                {column("description", t.description)}
                {column("currency", t.currency, false, s.currencyHelp)}
                {column("kind", t.kind, false, s.kindHelp)}
                {column("category", t.category)}
              </div>
            </details>
            <div className="p-actions">
              <button
                type="button"
                className="p-button-secondary"
                disabled={pending}
                onClick={() => {
                  setInspection(null);
                  setError("");
                }}
              >
                {s.back}
              </button>
              <button className="p-button" disabled={pending}>
                {pending ? t.loading : s.prepare}
              </button>
            </div>
          </form>
        ) : (
          <form className="p-stack" onSubmit={inspect}>
            <h3>{s.fileStep}</h3>
            <p>{s.intro}</p>
            <p className="p-muted">{s.supported}</p>
            <Field label={t.account}>
              <select
                value={accountId}
                required
                disabled={pending}
                onChange={(e) => {
                  setAccountId(e.target.value);
                  invalidate();
                }}
              >
                <option value="" disabled>
                  {s.choose}
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
                accept=".csv,.tsv,text/csv,text/tab-separated-values"
                disabled={pending}
                onChange={(e) => void readFile(e.target.files?.[0])}
              />
            </Field>
            {reading && <p role="status">{s.reading}</p>}
            <details>
              <summary>{s.paste}</summary>
              <Field label={t.csvText}>
                <textarea
                  rows={5}
                  value={csv}
                  maxLength={1_000_000}
                  disabled={pending}
                  onChange={(e) => {
                    fileEpoch.current++;
                    setReading(false);
                    setCsv(e.target.value);
                    setFileName("");
                    invalidate();
                  }}
                />
              </Field>
            </details>
            <details>
              <summary>{s.format}</summary>
              <div className="p-form-grid">
                <Field label={s.delimiter}>
                  <select
                    value={delimiter}
                    disabled={pending}
                    onChange={(e) => setDelimiter(e.target.value)}
                  >
                    <option value=",">{s.comma}</option>
                    <option value=";">{s.semicolon}</option>
                    <option value={"\t"}>{s.tab}</option>
                  </select>
                </Field>
                <Field label={s.headerRow}>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    required
                    value={headerRow}
                    disabled={pending}
                    onChange={(e) => setHeaderRow(Number(e.target.value))}
                  />
                </Field>
              </div>
            </details>
            <a
              className="p-button-ghost"
              href="/api/platform/transactions/sample.csv"
              download="argus-transactions.csv"
            >
              {t.sampleCsv}
            </a>
            <div className="p-actions">
              <button
                type="button"
                className="p-button-secondary"
                onClick={close}
                disabled={pending}
              >
                {t.cancel}
              </button>
              <button
                className="p-button"
                disabled={pending || reading || !accountId}
              >
                {pending ? t.loading : s.readColumns}
              </button>
            </div>
          </form>
        )}
        {error && (
          <p className="p-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
