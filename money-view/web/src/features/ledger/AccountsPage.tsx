import { useState, type FormEvent } from "react";
import { request } from "../../platform/client";
import { useRecordFocus } from "../../argus/useRecordFocus";
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
  accountSchema,
  accountsSchema,
  connectionSchema,
  connectionsSchema,
  connectorsSchema,
  deletedSchema,
  type Account,
} from "./contracts";
import { copy, categoryLabel, dateLabel } from "./copy";
import { ResourceState, useLedgerMutation, newKey } from "./shared";
import "./ledger.css";

const accountKinds = [
  "checking",
  "savings",
  "credit_card",
  "loan",
  "investment",
  "cash",
];
export function AccountsPage(props: PlatformPageProps) {
  const { locale, currency, revision, onChanged, onNavigate, query } = props,
    t = copy(locale);
  const [showDeleted, setShowDeleted] = useState(false),
    [editing, setEditing] = useState<Account | "new" | null>(null),
    [deleting, setDeleting] = useState<Account | null>(null);
  const targetId = query.get("record_id") ?? query.get("account_id");
  const accounts = useResource(
    () => targetId
      ? request(`/accounts/${encodeURIComponent(targetId)}`, accountSchema).then(account => ({ items: [account], total: 1, limit: 1, offset: 0 }))
      : request(
        `/accounts?currency=${encodeURIComponent(currency)}&include_deleted=${showDeleted}&limit=100`,
        accountsSchema,
      ),
    [currency, showDeleted, revision, targetId],
  );
  const recordRef = useRecordFocus(targetId, [accounts.data]);
  const connections = useResource(
    () => request("/connections", connectionsSchema),
    [revision],
  );
  const connectors = useResource(
    () => request("/connectors", connectorsSchema),
    [],
  );
  const mutation = useLedgerMutation(locale);
  const refresh = () => {
    accounts.reload();
    connections.reload();
    onChanged();
  };
  return (
    <div className="ledger-page p-stack" ref={recordRef}>
      <PageHeader
        title={t.accounts}
        description={t.accountsIntro}
        actions={
          <button className="p-button" onClick={() => setEditing("new")}>
            {t.addAccount}
          </button>
        }
      />
      <div className="p-toolbar">
        <span className="p-badge">{targetId ? accounts.data?.items[0]?.currency : currency}</span>
        {targetId && <button className="p-button-secondary" onClick={() => onNavigate("accounts")}>{locale === "en" ? "Show all accounts" : "Ver todas las cuentas"}</button>}
        <p className="p-muted">{t.noConversion}</p>
        <label className="ledger-checkbox">
          <input
            type="checkbox"
            checked={showDeleted}
            onChange={(e) => setShowDeleted(e.target.checked)}
          />
          {t.includeDeleted}
        </label>
      </div>
      {mutation.notice && (
        <p className="p-success" role="status">
          {mutation.notice}
        </p>
      )}
      {mutation.error && !deleting && (
        <p className="p-error" role="alert">
          {mutation.error}
        </p>
      )}
      <ResourceState {...accounts} retry={accounts.reload} locale={locale} />
      {accounts.data?.items.length === 0 && (
        <EmptyState
          title={t.noAccounts}
          description={t.noAccountsDetail}
          action={
            <button className="p-button" onClick={() => setEditing("new")}>
              {t.addAccount}
            </button>
          }
        />
      )}
      {accountKinds.map((kind) => {
        const items = accounts.data?.items.filter((a) => a.kind === kind) ?? [];
        return items.length ? (
          <Panel key={kind} className="ledger-account-group">
            <h2>{categoryLabel(kind, locale)}</h2>
            <div className="p-ledger">
              {items.map((account) => (
                <article className="p-ledger-row" key={account.id} data-record-id={account.id} tabIndex={-1}>
                  <div className="p-row-main">
                    <h3>
                      {account.name}{" "}
                      {account.deleted_at && (
                        <span className="p-badge">{t.deleted}</span>
                      )}
                    </h3>
                    <p className="p-muted">
                      {account.institution} · {account.currency}
                    </p>
                    <EvidenceLine evidence={account.source} locale={locale} />
                  </div>
                  <div className="p-row-value">
                    <Money
                      amount={account.balance}
                      currency={account.currency}
                      locale={locale}
                    />
                  </div>
                  <div className="p-row-actions">
                    {account.deleted_at ? (
                      <button
                        className="p-button-secondary"
                        disabled={mutation.pending}
                        onClick={() =>
                          void mutation.run(
                            () =>
                              request(
                                `/accounts/${account.id}/restore`,
                                accountSchema,
                                { method: "POST" },
                              ),
                            refresh,
                          )
                        }
                      >
                        {t.restore}
                      </button>
                    ) : (
                      <>
                        <button
                          className="p-button-ghost"
                          onClick={() =>
                            onNavigate("transactions", {
                              account_id: account.id,
                            })
                          }
                        >
                          {t.viewTransactions}
                        </button>
                        <button
                          className="p-button-ghost"
                          onClick={() => setEditing(account)}
                          aria-label={`${t.edit}: ${account.name}`}
                        >
                          {t.edit}
                        </button>
                        <button
                          className="p-button-ghost"
                          onClick={() => setDeleting(account)}
                          aria-label={`${t.remove}: ${account.name}`}
                        >
                          {t.remove}
                        </button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </Panel>
        ) : null;
      })}
      <Panel>
        <h2>{t.connectors}</h2>
        <p className="p-muted">{t.connectorsIntro}</p>
        <ResourceState
          loading={connections.loading || connectors.loading}
          error={connections.error || connectors.error}
          retry={() => {
            connections.reload();
            connectors.reload();
          }}
          locale={locale}
        />
        <div className="p-ledger">
          {connectors.data?.items.map((connector) => {
            const connection = connections.data?.items.find(
              (item) => item.connector_id === connector.id,
            );
            return (
              <article className="p-ledger-row" key={connector.id}>
                <div className="p-row-main">
                  <h3>{connector.name}</h3>
                  <p className="p-muted">
                    {connector.countries.join(", ")} ·{" "}
                    {connector.currencies.join(", ")}
                  </p>
                  {connection && (
                    <>
                      <p className="p-muted">
                        {t.lastGood}:{" "}
                        {connection.last_good_at
                          ? dateLabel(connection.last_good_at, locale)
                          : t.never}
                      </p>
                      <p
                        className={
                          connection.error_code ? "p-error" : "p-muted"
                        }
                      >
                        {connection.error_code ? t.failedSync : t.connected}
                      </p>
                    </>
                  )}
                </div>
                <div className="p-row-actions">
                  {connection ? (
                    <>
                      <button
                        className="p-button-secondary"
                        disabled={mutation.pending}
                        onClick={() =>
                          void mutation.run(
                            () =>
                              request(
                                `/connections/${connection.id}/sync`,
                                connectionSchema,
                                {
                                  method: "POST",
                                  body: JSON.stringify({
                                    outcome: "success",
                                    idempotency_key: newKey(),
                                  }),
                                },
                              ),
                            refresh,
                          )
                        }
                      >
                        {t.refresh}
                      </button>
                      <button
                        className="p-button-ghost"
                        disabled={mutation.pending}
                        onClick={() =>
                          void mutation.run(
                            () =>
                              request(
                                `/connections/${connection.id}/sync`,
                                connectionSchema,
                                {
                                  method: "POST",
                                  body: JSON.stringify({
                                    outcome: "failure",
                                    idempotency_key: newKey(),
                                  }),
                                },
                              ),
                            refresh,
                          )
                        }
                      >
                        {t.failSync}
                      </button>
                    </>
                  ) : (
                    <button
                      className="p-button-secondary"
                      disabled={mutation.pending}
                      onClick={() =>
                        void mutation.run(
                          () =>
                            request("/connections", connectionSchema, {
                              method: "POST",
                              body: JSON.stringify({
                                connector_id: connector.id,
                                idempotency_key: newKey(),
                              }),
                            }),
                          refresh,
                        )
                      }
                    >
                      {t.connect}
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </Panel>
      {editing && (
        <AccountEditor
          key={editing === "new" ? "new" : editing.id}
          account={editing === "new" ? null : editing}
          {...props}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
      {deleting && (
        <Modal
          title={t.confirmRemove}
          onClose={() => !mutation.pending && setDeleting(null)}
          destructive
        >
          <p>{deleting.name}</p>
          <p>{t.deletedExplain}</p>
          {mutation.error && (
            <p className="p-error" role="alert">
              {mutation.error}
            </p>
          )}
          <div className="p-actions">
            <button
              className="p-button-secondary"
              data-modal-cancel
              disabled={mutation.pending}
              onClick={() => setDeleting(null)}
            >
              {t.cancel}
            </button>
            <button
              className="p-button-danger"
              disabled={mutation.pending}
              onClick={() =>
                void mutation.run(
                  () =>
                    request(`/accounts/${deleting.id}`, deletedSchema, {
                      method: "DELETE",
                    }),
                  () => {
                    setDeleting(null);
                    refresh();
                  },
                )
              }
            >
              {mutation.pending ? t.saving : t.remove}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function AccountEditor({
  account,
  locale,
  currency,
  onClose,
  onSaved,
}: {
  account: Account | null;
  onClose: () => void;
  onSaved: () => void;
} & PlatformPageProps) {
  const t = copy(locale),
    mutation = useLedgerMutation(locale),
    [idempotencyKey] = useState(newKey);
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    void mutation.run(
      () =>
        request(
          account ? `/accounts/${account.id}` : "/accounts",
          accountSchema,
          {
            method: account ? "PATCH" : "POST",
            body: JSON.stringify(
              account
                ? { name: values.name, institution: values.institution }
                : { ...values, idempotency_key: idempotencyKey },
            ),
          },
        ),
      onSaved,
    );
  }
  return (
    <Modal
      title={account ? t.editAccount : t.addAccount}
      onClose={() => !mutation.pending && onClose()}
    >
      <form className="p-stack" onSubmit={submit}>
        <div className="p-form-grid">
          <Field label={t.name}>
            <input
              name="name"
              required
              maxLength={120}
              defaultValue={account?.name}
            />
          </Field>
          <Field label={t.institution}>
            <input
              name="institution"
              required
              maxLength={120}
              defaultValue={account?.institution}
            />
          </Field>
          {!account && (
            <>
              <Field label={t.kind}>
                <select name="kind" defaultValue="checking">
                  {accountKinds.map((kind) => (
                    <option key={kind} value={kind}>
                      {categoryLabel(kind, locale)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t.currency}>
                <input
                  name="currency"
                  required
                  pattern="[A-Z]{3}"
                  maxLength={3}
                  defaultValue={currency}
                />
              </Field>
              <Field label={t.opening}>
                <input
                  name="opening_balance"
                  required
                  type="number"
                  step="any"
                  defaultValue="0.00"
                />
              </Field>
            </>
          )}
        </div>
        {mutation.error && (
          <p className="p-error" role="alert">
            {mutation.error}
          </p>
        )}
        <div className="p-actions">
          <button
            type="button"
            className="p-button-secondary"
            onClick={onClose}
            disabled={mutation.pending}
          >
            {t.cancel}
          </button>
          <button className="p-button" disabled={mutation.pending}>
            {mutation.pending ? t.saving : t.save}
          </button>
        </div>
      </form>
    </Modal>
  );
}
