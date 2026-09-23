import { useEffect, useRef, useState, type FormEvent } from "react";
import { request, requestResponse } from "../../platform/client";
import { useResource } from "../../platform/hooks";
import {
  PageHeader,
  Panel,
  Modal,
  Field,
  EvidenceLine,
  Money,
  EmptyState,
} from "../../platform/ui";
import type { PlatformPageProps } from "../../platform/types";
import {
  accountsSchema,
  categoriesSchema,
  transactionsSchema,
  transactionSchema,
  deletedSchema,
  type Transaction,
} from "./contracts";
import { copy, categoryLabel, dateLabel } from "./copy";
import { ResourceState, useLedgerMutation, newKey } from "./shared";
import { ImportDialog } from "./ImportDialog";
import "./ledger.css";

export function TransactionsPage(props: PlatformPageProps) {
  const { locale, currency, query, revision, onNavigate, onChanged } = props,
    t = copy(locale);
  const [search, setSearch] = useState(query.get("q") || ""),
    [selected, setSelected] = useState<Transaction | "new" | null>(null),
    [importing, setImporting] = useState(false),
    [deleted, setDeleted] = useState<Transaction | null>(null);
  const mutation = useLedgerMutation(locale);
  const targetId = query.get("record_id");
  const importRequested = query.get("import") === "1";
  const [targetLoading, setTargetLoading] = useState(false);
  const [targetFailed, setTargetFailed] = useState(false);
  const [targetAttempt, setTargetAttempt] = useState(0);
  const detailRequest = useRef<AbortController | null>(null);
  useEffect(() => {
    detailRequest.current?.abort();
    setTargetFailed(false);
    if (!targetId || importRequested) {
      setTargetLoading(false);
      return;
    }
    const controller = new AbortController();
    detailRequest.current = controller;
    setSelected(null);
    setTargetLoading(true);
    void request(
      `/transactions/${encodeURIComponent(targetId)}`,
      transactionSchema,
      { signal: controller.signal },
    )
      .then((transaction) => {
        if (!controller.signal.aborted) setSelected(transaction);
      })
      .catch(() => {
        if (!controller.signal.aborted) setTargetFailed(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setTargetLoading(false);
      });
    return () => controller.abort();
  }, [targetId, importRequested, revision, targetAttempt]);
  const closeDetail = () => {
    detailRequest.current?.abort();
    setSelected(null);
    setTargetLoading(false);
    setTargetFailed(false);
    if (query.has("record_id")) {
      const next = new URLSearchParams(query);
      next.delete("record_id");
      onNavigate("transactions", Object.fromEntries(next));
    }
  };
  const openDetail = (id: string) => {
    const next = new URLSearchParams(query);
    next.set("record_id", id);
    onNavigate("transactions", Object.fromEntries(next));
  };
  const [importAccounts, setImportAccounts] = useState<Account[] | null>(null);
  const openedImport = useRef<string | null>(null);
  const importQuery = query.toString();
  useEffect(() => {
    if (query.get("import") !== "1") {
      openedImport.current = null;
      return;
    }
    if (openedImport.current === importQuery) return;
    const controller = new AbortController();
    void request("/accounts?limit=100", accountsSchema, {
      signal: controller.signal,
    })
      .then((result) => {
        if (controller.signal.aborted) return;
        openedImport.current = importQuery;
        setImportAccounts(result.items);
        setImporting(true);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          openedImport.current = importQuery;
          mutation.setError(t.loadError);
        }
      });
    return () => controller.abort();
  }, [importQuery]);
  const closeImport = () => {
    setImporting(false);
    setImportAccounts(null);
    if (query.has("import")) {
      const next = new URLSearchParams(query);
      next.delete("import");
      onNavigate("transactions", Object.fromEntries(next));
    }
  };
  const params = new URLSearchParams(query);
  params.set("currency", currency);
  if (!params.has("limit")) params.set("limit", "25");
  if (!params.has("sort")) params.set("sort", "date_desc");
  const queryString = params.toString();
  const records = useResource(
    () => request(`/transactions?${queryString}`, transactionsSchema),
    [queryString, revision],
  );
  const accounts = useResource(
    () =>
      request(
        `/accounts?currency=${encodeURIComponent(currency)}&limit=100`,
        accountsSchema,
      ),
    [currency, revision],
  );
  const categories = useResource(
    () => request("/categories", categoriesSchema),
    [],
  );
  useEffect(() => setSearch(query.get("q") || ""), [query.get("q")]);
  const update = (changes: Record<string, string>, reset = true) => {
    const next = new URLSearchParams(query);
    Object.entries(changes).forEach(([key, value]) =>
      value ? next.set(key, value) : next.delete(key),
    );
    if (reset) next.delete("offset");
    onNavigate("transactions", Object.fromEntries(next));
  };
  const refresh = () => {
    records.reload();
    onChanged();
  };
  const limit = records.data?.limit || Number(params.get("limit")),
    offset = records.data?.offset || Number(params.get("offset") || 0),
    total = records.data?.total || 0;
  useEffect(() => {
    if (records.data && !records.loading && offset >= total && offset > 0)
      update(
        { offset: String(Math.max(0, Math.ceil(total / limit) - 1) * limit) },
        false,
      );
  }, [total, offset, limit, records.loading]);
  async function exportCsv() {
    await mutation.run(async () => {
      const response = await requestResponse(
        `/transactions/export.csv?${queryString}`,
      );
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "argus-transactions.csv";
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    });
  }
  return (
    <div className="ledger-page p-stack">
      <PageHeader
        title={t.transactions}
        description={t.transactionsIntro}
        actions={
          <div className="p-actions">
            <button
              className="p-button-secondary"
              onClick={() => {
                setImportAccounts(null);
                setImporting(true);
              }}
            >
              {t.importCsv}
            </button>
            <button
              className="p-button"
              onClick={() => {
                closeDetail();
                setSelected("new");
              }}
            >
              {t.addTransaction}
            </button>
          </div>
        }
      />
      {targetLoading && (
        <p className="p-muted" role="status">
          {t.loading}{" "}
          <button className="p-button-ghost" onClick={closeDetail}>
            {t.cancel}
          </button>
        </p>
      )}
      {targetFailed && (
        <div className="p-error" role="alert">
          <p>
            {locale === "en"
              ? "This transaction is unavailable. It may have been deleted, or its account may no longer be active."
              : "Este movimiento no está disponible. Puede haberse eliminado o su cuenta puede estar inactiva."}
          </p>
          <div className="p-actions">
            <button
              className="p-button-secondary"
              onClick={() => setTargetAttempt((attempt) => attempt + 1)}
            >
              {t.retry}
            </button>
            <button className="p-button-ghost" onClick={closeDetail}>
              {t.cancel}
            </button>
          </div>
        </div>
      )}
      <Panel className="ledger-filters">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            update({ q: search });
          }}
          className="ledger-search"
        >
          <Field label={t.search}>
            <input
              type="search"
              maxLength={200}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Field>
          <button className="p-button-secondary" type="submit">
            {locale === "en" ? "Search" : "Buscar"}
          </button>
        </form>
        <div className="p-form-grid">
          <Field label={t.account}>
            <select
              value={query.get("account_id") || ""}
              onChange={(e) => update({ account_id: e.target.value })}
            >
              <option value="">{t.allAccounts}</option>
              {accounts.data?.items.map((account) => (
                <option value={account.id} key={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t.category}>
            <select
              value={query.get("category") || ""}
              onChange={(e) => update({ category: e.target.value })}
            >
              <option value="">{t.allCategories}</option>
              {categories.data?.items.map((category) => (
                <option key={category.id} value={category.id}>
                  {categoryLabel(category.id, locale)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t.from}>
            <input
              type="date"
              value={query.get("date_from") || ""}
              onChange={(e) => update({ date_from: e.target.value })}
            />
          </Field>
          <Field label={t.to}>
            <input
              type="date"
              value={query.get("date_to") || ""}
              onChange={(e) => update({ date_to: e.target.value })}
            />
          </Field>
          <Field label={t.status}>
            <select
              value={query.get("status") || ""}
              onChange={(e) => update({ status: e.target.value })}
            >
              <option value="">{t.allStatuses}</option>
              <option value="posted">{t.posted}</option>
              <option value="pending">{t.pending}</option>
            </select>
          </Field>
          <Field label={t.sort}>
            <select
              value={params.get("sort")!}
              onChange={(e) => update({ sort: e.target.value })}
            >
              {["date_desc", "date_asc", "amount_desc", "amount_asc"].map(
                (sort) => (
                  <option key={sort} value={sort}>
                    {categoryLabel(sort, locale)}
                  </option>
                ),
              )}
            </select>
          </Field>
        </div>
        <div className="p-actions">
          <button
            className="p-button-ghost"
            onClick={() => onNavigate("transactions")}
          >
            {t.clearFilters}
          </button>
          <button
            className="p-button-ghost"
            onClick={() => void exportCsv()}
            disabled={mutation.pending}
          >
            {t.exportCsv}
          </button>
          <span className="p-badge">{currency}</span>
          {query.get("merchant") && (
            <span className="p-badge">
              {t.merchant}: {query.get("merchant")}
            </span>
          )}
          {query.get("spending_only") === "true" && (
            <span className="p-badge">{t.spending}</span>
          )}
        </div>
        <ResourceState
          loading={accounts.loading || categories.loading}
          error={accounts.error || categories.error}
          retry={() => {
            accounts.reload();
            categories.reload();
          }}
          locale={locale}
        />
      </Panel>
      {mutation.error && (
        <p className="p-error" role="alert">
          {mutation.error}
        </p>
      )}
      {mutation.notice && (
        <p className="p-success" role="status">
          {mutation.notice}
        </p>
      )}
      {deleted && (
        <p className="p-success" role="status">
          {t.removed}{" "}
          <button
            className="p-button-ghost"
            disabled={mutation.pending}
            onClick={() =>
              void mutation.run(
                () =>
                  request(
                    `/transactions/${deleted.id}/restore`,
                    transactionSchema,
                    { method: "POST" },
                  ),
                () => {
                  setDeleted(null);
                  refresh();
                },
              )
            }
          >
            {t.undo}
          </button>
        </p>
      )}
      {records.data?.aggregates.map((summary) => (
        <Panel key={summary.currency}>
          <h2>{t.filteredTotals}</h2>
          <div className="p-metrics">
            {(["income", "spending", "net"] as const).map((metric) => (
              <div className="p-metric" key={metric}>
                <small>{t[metric]}</small>
                <strong>
                  <Money
                    amount={summary[metric]}
                    currency={summary.currency}
                    locale={locale}
                  />
                </strong>
              </div>
            ))}
          </div>
          <p className="p-muted">{t.transferNote}</p>
          <EvidenceLine evidence={summary.source} locale={locale} />
        </Panel>
      ))}
      <Panel>
        <ResourceState {...records} retry={records.reload} locale={locale} />
        {records.data?.items.length === 0 && (
          <EmptyState
            title={t.noTransactions}
            action={
              <button
                className="p-button-secondary"
                onClick={() => onNavigate("transactions")}
              >
                {t.clearFilters}
              </button>
            }
          />
        )}
        {Boolean(records.data?.items.length) && (
          <>
            <div className="p-toolbar">
              <p>
                {total.toLocaleString(locale)} {t.matches}
              </p>
              <Field label={t.perPage}>
                <select
                  value={params.get("limit")!}
                  onChange={(e) => update({ limit: e.target.value })}
                >
                  {[25, 50, 100].map((count) => (
                    <option key={count} value={count}>
                      {count}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="ledger-table-wrap">
              <table className="ledger-table">
                <thead>
                  <tr>
                    <th
                      scope="col"
                      aria-sort={
                        params.get("sort") === "date_desc"
                          ? "descending"
                          : params.get("sort") === "date_asc"
                            ? "ascending"
                            : "none"
                      }
                    >
                      <button
                        className="p-button-ghost"
                        onClick={() =>
                          update({
                            sort:
                              params.get("sort") === "date_desc"
                                ? "date_asc"
                                : "date_desc",
                          })
                        }
                      >
                        {t.date}
                      </button>
                    </th>
                    <th scope="col">{t.merchant}</th>
                    <th scope="col">{t.category}</th>
                    <th
                      scope="col"
                      aria-sort={
                        params.get("sort") === "amount_desc"
                          ? "descending"
                          : params.get("sort") === "amount_asc"
                            ? "ascending"
                            : "none"
                      }
                    >
                      <button
                        className="p-button-ghost"
                        onClick={() =>
                          update({
                            sort:
                              params.get("sort") === "amount_desc"
                                ? "amount_asc"
                                : "amount_desc",
                          })
                        }
                      >
                        {t.amount}
                      </button>
                    </th>
                    <th scope="col">{t.details}</th>
                  </tr>
                </thead>
                <tbody>
                  {records.data?.items.map((row) => (
                    <tr key={row.id}>
                      <td data-label={t.date}>
                        {dateLabel(row.date, locale)}
                        {row.status === "pending" && (
                          <span className="p-badge">{t.pending}</span>
                        )}
                      </td>
                      <td data-label={t.merchant}>
                        <strong>{row.merchant}</strong>
                        <span className="ledger-subline">
                          {row.account_name}
                        </span>
                        <span className="ledger-subline">
                          {row.description}
                        </span>
                      </td>
                      <td data-label={t.category}>
                        {row.splits.length
                          ? row.splits
                              .map((split) =>
                                categoryLabel(split.category, locale),
                              )
                              .join(" · ")
                          : categoryLabel(row.category, locale)}
                      </td>
                      <td data-label={t.amount} className="ledger-amount">
                        <Money
                          amount={row.amount}
                          currency={row.currency}
                          locale={locale}
                        />
                      </td>
                      <td>
                        <button
                          className="p-button-ghost"
                          onClick={() => openDetail(row.id)}
                          aria-label={`${t.details}: ${row.merchant}, ${dateLabel(row.date, locale)}`}
                        >
                          {t.details}
                        </button>
                        <EvidenceLine evidence={row.source} locale={locale} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <nav
              className="p-pagination"
              aria-label={
                locale === "en" ? "Transaction pages" : "Páginas de movimientos"
              }
            >
              <button
                className="p-button-secondary"
                disabled={offset === 0 || records.loading}
                onClick={() =>
                  update({ offset: String(Math.max(0, offset - limit)) }, false)
                }
              >
                {t.previous}
              </button>
              <span>
                {t.page} {Math.floor(offset / limit) + 1} {t.of}{" "}
                {Math.max(1, Math.ceil(total / limit))}
                <span className="ledger-subline">
                  {offset + 1}–{Math.min(offset + limit, total)} {t.of}{" "}
                  {total.toLocaleString(locale)}
                </span>
              </span>
              <button
                className="p-button-secondary"
                disabled={offset + limit >= total || records.loading}
                onClick={() =>
                  update({ offset: String(offset + limit) }, false)
                }
              >
                {t.next}
              </button>
            </nav>
          </>
        )}
      </Panel>
      {selected && (
        <TransactionEditor
          key={selected === "new" ? "new" : selected.id}
          transaction={selected === "new" ? null : selected}
          accounts={accounts.data?.items ?? []}
          categories={categories.data?.items ?? []}
          {...props}
          onClose={closeDetail}
          onSaved={() => {
            closeDetail();
            refresh();
          }}
          onDeleted={(row) => {
            closeDetail();
            setDeleted(row);
            refresh();
          }}
        />
      )}
      {importing && (
        <ImportDialog
          {...props}
          accounts={importAccounts ?? accounts.data?.items ?? []}
          onClose={closeImport}
          onImported={() => {
            closeImport();
            refresh();
          }}
        />
      )}
    </div>
  );
}

import type { Account } from "./contracts";
function TransactionEditor({
  transaction,
  accounts,
  categories,
  locale,
  onClose,
  onSaved,
  onDeleted,
}: {
  transaction: Transaction | null;
  accounts: Account[];
  categories: { id: string; kind: string }[];
  onClose: () => void;
  onSaved: () => void;
  onDeleted: (row: Transaction) => void;
} & PlatformPageProps) {
  const t = copy(locale),
    mutation = useLedgerMutation(locale),
    [splits, setSplits] = useState(transaction?.splits ?? []),
    [confirm, setConfirm] = useState<"delete" | "reverse" | null>(null),
    [kind, setKind] = useState(transaction?.kind ?? "expense"),
    [category, setCategory] = useState(transaction?.category ?? "other"),
    [accountId, setAccountId] = useState(accounts[0]?.id ?? ""),
    [idempotencyKey] = useState(newKey);
  const account = accounts.find((item) => item.id === accountId);
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    if (confirm) return;
    void mutation.run(
      () =>
        request(
          transaction ? `/transactions/${transaction.id}` : "/transactions",
          transactionSchema,
          {
            method: transaction ? "PATCH" : "POST",
            body: JSON.stringify({
              ...values,
              splits,
              ...(!transaction ? { idempotency_key: idempotencyKey } : {}),
            }),
          },
        ),
      onSaved,
    );
  }
  const categorySelect = (value: string, onChange: (value: string) => void) => (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {categories
        .filter((item) => item.kind === "expense")
        .map((item) => (
          <option value={item.id} key={item.id}>
            {categoryLabel(item.id, locale)}
          </option>
        ))}
    </select>
  );
  return (
    <Modal
      title={transaction ? t.detail : t.addTransaction}
      onClose={() => !mutation.pending && onClose()}
    >
      <form className="p-stack" onSubmit={submit}>
        {transaction ? (
          <>
            <div className="ledger-detail-amount">
              <Money
                amount={transaction.amount}
                currency={transaction.currency}
                locale={locale}
              />
            </div>
            <p>
              {transaction.merchant} · {dateLabel(transaction.date, locale)} ·{" "}
              {transaction.account_name}
            </p>
            <EvidenceLine evidence={transaction.source} locale={locale} />
          </>
        ) : (
          <>
            <p className="p-muted">{t.manualNote}</p>
            <div className="p-form-grid">
              <Field label={t.account}>
                <select
                  name="account_id"
                  value={accountId}
                  onChange={(e) => setAccountId(e.target.value)}
                  required
                >
                  <option value="" disabled>
                    {t.account}
                  </option>
                  {accounts.map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.name} ({item.currency})
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t.date}>
                <input
                  name="date"
                  type="date"
                  required
                  defaultValue={new Date().toISOString().slice(0, 10)}
                />
              </Field>
              <Field label={t.merchant}>
                <input name="merchant" required maxLength={160} />
              </Field>
              <Field
                label={`${t.amount}${account ? ` (${account.currency})` : ""}`}
              >
                <input name="amount" type="number" step="any" required />
              </Field>
              <Field label={t.kind}>
                <select
                  name="kind"
                  value={kind}
                  onChange={(e) => {
                    const next = e.target.value;
                    setKind(next);
                    setSplits([]);
                    setCategory(
                      next === "income"
                        ? "income"
                        : next === "transfer"
                          ? "transfer"
                          : "other",
                    );
                  }}
                >
                  {[
                    "expense",
                    "income",
                    "refund",
                    "transfer",
                    "adjustment",
                  ].map((value) => (
                    <option key={value} value={value}>
                      {categoryLabel(value, locale)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t.status}>
                <select name="status">
                  <option value="posted">{t.posted}</option>
                  <option value="pending">{t.pending}</option>
                </select>
              </Field>
              {kind === "transfer" && (
                <Field label={t.destination}>
                  <select name="to_account_id" required defaultValue="">
                    <option value="" disabled>
                      {t.destination}
                    </option>
                    {accounts
                      .filter(
                        (item) =>
                          item.id !== accountId &&
                          item.currency === account?.currency,
                      )
                      .map((item) => (
                        <option value={item.id} key={item.id}>
                          {item.name}
                        </option>
                      ))}
                  </select>
                </Field>
              )}
            </div>
          </>
        )}
        <div className="p-form-grid">
          <Field label={t.category}>
            <select
              name="category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {categories
                .filter(
                  (item) =>
                    kind === "adjustment" ||
                    item.kind ===
                      (kind === "income"
                        ? "income"
                        : kind === "transfer"
                          ? "transfer"
                          : "expense"),
                )
                .map((item) => (
                  <option value={item.id} key={item.id}>
                    {categoryLabel(item.id, locale)}
                  </option>
                ))}
            </select>
          </Field>
          <Field label={t.description}>
            <input
              name="description"
              maxLength={500}
              defaultValue={transaction?.description || ""}
            />
          </Field>
        </div>
        <Field label={t.notes}>
          <textarea
            name="notes"
            rows={3}
            maxLength={1000}
            defaultValue={transaction?.notes || ""}
          />
        </Field>
        {(kind === "expense" || kind === "refund") && (
          <fieldset className="ledger-splits">
            <legend>{t.split}</legend>
            <p className="p-muted">{t.splitNote}</p>
            {splits.map((split, index) => (
              <div className="ledger-split" key={index}>
                <Field label={`${t.category} ${index + 1}`}>
                  {categorySelect(split.category, (value) =>
                    setSplits((current) =>
                      current.map((item, i) =>
                        i === index ? { ...item, category: value } : item,
                      ),
                    ),
                  )}
                </Field>
                <Field label={`${t.amount} ${index + 1}`}>
                  <input
                    type="number"
                    step="any"
                    required
                    value={split.amount}
                    onChange={(e) =>
                      setSplits((current) =>
                        current.map((item, i) =>
                          i === index
                            ? { ...item, amount: e.target.value }
                            : item,
                        ),
                      )
                    }
                  />
                </Field>
                <button
                  type="button"
                  className="p-button-ghost"
                  onClick={() =>
                    setSplits((current) =>
                      current.filter((_, i) => i !== index),
                    )
                  }
                  aria-label={`${t.removeSplit} ${index + 1}`}
                >
                  {t.removeSplit}
                </button>
              </div>
            ))}
            <button
              type="button"
              className="p-button-secondary"
              disabled={splits.length >= 20}
              onClick={() =>
                setSplits((current) => [
                  ...current,
                  { category: "other", amount: "" },
                ])
              }
            >
              {t.addSplit}
            </button>
          </fieldset>
        )}
        {mutation.error && (
          <p className="p-error" role="alert">
            {mutation.error}
          </p>
        )}
        {confirm && transaction ? (
          <div className="ledger-confirm">
            <p>
              {confirm === "delete" ? t.deleteTransactionNote : t.reverseNote}
            </p>
            <div className="p-actions">
              <button
                type="button"
                className="p-button-secondary"
                disabled={mutation.pending}
                onClick={() => setConfirm(null)}
              >
                {t.cancel}
              </button>
              <button
                type="button"
                className="p-button-danger"
                disabled={mutation.pending}
                onClick={() =>
                  void mutation.run(
                    () =>
                      confirm === "delete"
                        ? request(
                            `/transactions/${transaction.id}`,
                            deletedSchema,
                            { method: "DELETE" },
                          )
                        : request(
                            `/transactions/${transaction.id}/reverse`,
                            transactionSchema,
                            {
                              method: "POST",
                              body: JSON.stringify({
                                idempotency_key: idempotencyKey,
                              }),
                            },
                          ),
                    () =>
                      confirm === "delete" ? onDeleted(transaction) : onSaved(),
                  )
                }
              >
                {mutation.pending
                  ? t.saving
                  : confirm === "delete"
                    ? t.deleteTransaction
                    : t.reverse}
              </button>
            </div>
          </div>
        ) : (
          <div className="p-actions">
            <button
              type="button"
              className="p-button-secondary"
              onClick={onClose}
              disabled={mutation.pending}
            >
              {t.cancel}
            </button>
            <button
              className="p-button"
              disabled={mutation.pending || (!transaction && !accounts.length)}
            >
              {mutation.pending ? t.saving : t.save}
            </button>
            {transaction && (
              <>
                <button
                  type="button"
                  className="p-button-ghost"
                  onClick={() => setConfirm("delete")}
                >
                  {t.deleteTransaction}
                </button>
                {transaction.status === "posted" &&
                  transaction.kind !== "transfer" &&
                  !transaction.reversal_of && (
                    <button
                      type="button"
                      className="p-button-ghost"
                      onClick={() => setConfirm("reverse")}
                    >
                      {t.reverse}
                    </button>
                  )}
              </>
            )}
          </div>
        )}
      </form>
    </Modal>
  );
}
