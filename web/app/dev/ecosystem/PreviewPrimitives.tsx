import type { ReactNode } from "react";
import { Banknote, Building2, ChevronRight, CircleHelp, CreditCard, Landmark, PiggyBank, Wallet } from "lucide-react";
import { type AccountType, type PreviewCopy, type SampleAccount } from "./preview-content";
import styles from "./ecosystem-preview.module.css";

export function AccountIcon({ type }: { type: AccountType }) {
  const Icon = { cash: Banknote, checking: Landmark, savings: PiggyBank, investments: Building2, credit: CreditCard, debt: Wallet }[type];
  return <Icon aria-hidden="true" size={21} strokeWidth={1.6} />;
}

export function Money({ account, copy }: { account: SampleAccount; copy: PreviewCopy }) {
  return <span className={styles.accountMoney}>{account.balance === null ? copy.unknownBalance : <>{account.currency} <span>{account.balance}</span></>}{account.isDebt ? <small>{copy.owed}</small> : null}</span>;
}

export function AccountRow({ account, copy, onClick }: { account: SampleAccount; copy: PreviewCopy; onClick: () => void }) {
  return <button type="button" className={styles.accountRow} onClick={onClick}>
    <span className={styles.accountIcon}><AccountIcon type={account.type} /></span>
    <span className={styles.rowText}><strong>{copy[account.name]}</strong><small>{copy[account.type]} · {copy.asOf}</small></span>
    <Money account={account} copy={copy} /><ChevronRight className={styles.rowChevron} size={17} aria-hidden="true" />
  </button>;
}

export function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return <div className={styles.detailRow}><dt>{label}</dt><dd>{children}</dd></div>;
}

export function EmptyState({ title, body, action, onAction, children }: { title: string; body: string; action?: string; onAction?: () => void; children?: ReactNode }) {
  return <section className={styles.emptyState}><div className={styles.emptyIcon}>{children ?? <CircleHelp size={28} strokeWidth={1.3} />}</div><h2>{title}</h2><p>{body}</p>{action && onAction ? <button className={styles.primaryButton} onClick={onAction}>{action}</button> : null}</section>;
}
