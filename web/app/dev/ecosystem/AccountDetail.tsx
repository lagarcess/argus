"use client";

import { useEffect, useId, useRef } from "react";
import { ArrowDownLeft, ArrowLeftRight, ArrowUpRight, ChevronRight, LockKeyhole, X } from "lucide-react";
import { SAMPLE, type PreviewCopy, type SampleAccount } from "./preview-content";
import { AccountIcon, DetailRow, Money } from "./PreviewPrimitives";
import styles from "./ecosystem-preview.module.css";

type DetailProps = {
  account: SampleAccount; copy: PreviewCopy;
  onEdit: () => void; onCorrection: () => void; onActivity: (account: SampleAccount) => void;
};

/** One read-only body for the desktop inspector and the existing detail sheet. */
export default function AccountDetail({ account, copy, onEdit, onCorrection, onActivity }: DetailProps) {
  const activity = SAMPLE.activity.filter((item) => item.account === account.id);
  return <div data-testid="account-detail" className={styles.accountDetail}>
    <p className={styles.eyebrow}>{copy.localOnly}</p>
    <div className={styles.detailBalance}><AccountIcon type={account.type} /><div><span className={styles.muted}>{account.isDebt ? copy.balanceOwed : copy.balance}</span><Money account={account} copy={copy} /></div></div>
    <p className={styles.fine}>{copy.recordedAsOf}</p>
    <div className={styles.buttonRow}>
      <button className={styles.primaryButton} onClick={onEdit}>{copy.editDetails}</button>
      {account.id === "everyday" ? <button className={styles.secondaryButton} onClick={onCorrection}>{copy.checkBalance}</button> : null}
    </div>
    <dl className={styles.details}>
      <DetailRow label={copy.type}>{copy[account.type]}</DetailRow>
      <DetailRow label={copy.currency}>{account.currency}</DetailRow>
      <DetailRow label={copy.source}>{copy.manualSource}</DetailRow>
      <DetailRow label={copy.account}>{copy.individual}</DetailRow>
    </dl>
    <p className={styles.inlineNote}><LockKeyhole size={16} aria-hidden="true" />{copy.private}</p>
    <p className={styles.fine}>{copy.samplePrivacy}</p>
    <div className={styles.sectionHeading}><h3>{copy.recentActivity}</h3><button className={styles.textButton} onClick={() => onActivity(account)}>{copy.viewAll}<ChevronRight size={16} aria-hidden="true" /></button></div>
    {activity.length ? activity.map((item) => <div className={styles.activityRow} key={item.id}>
      <span className={styles.smallIcon}>{item.id === "transfer" ? <ArrowLeftRight size={18} /> : item.id === "income" ? <ArrowDownLeft size={18} /> : <ArrowUpRight size={18} />}</span>
      <span className={styles.rowText}><strong>{copy[item.title]}</strong><small>{copy.yesterday}</small></span>
      <span className={styles.amount}>{item.amount}</span>
    </div>) : <div className={styles.quietBox}><strong>{copy.noActivity}</strong><p>{copy.openingBalance}</p></div>}
  </div>;
}

export function AccountInspector({ onClose, ...props }: DetailProps & { onClose: () => void }) {
  const titleId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => { headingRef.current?.focus(); }, [props.account.id]);
  return <aside className={styles.accountInspector} aria-labelledby={titleId} data-testid="account-inspector" onKeyDown={(event) => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onClose(); }
  }}>
    <div className={styles.inspectorHeading}><h2 ref={headingRef} id={titleId} tabIndex={-1}>{props.copy[props.account.name]}</h2><button type="button" className={styles.iconButton} aria-label={props.copy.closeAccountDetails} onClick={onClose}><X size={18} aria-hidden="true" /></button></div>
    <AccountDetail {...props} />
  </aside>;
}
