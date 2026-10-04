"use client";

import { useState, type ReactNode } from "react";
import { ArrowDownLeft, ArrowLeftRight, ArrowUpRight, Bell, CalendarDays, Check, ChevronRight, CircleHelp, FileText, Globe2, Landmark, LockKeyhole, Plus, Search, Settings2, ShieldCheck, SlidersHorizontal, Target, UserRound, Wallet } from "lucide-react";
import { SAMPLE, RECENTS, type CopyKey, type PreviewCopy, type PreviewState, type PreviewView, type RecentId, type SampleAccount } from "./preview-content";
import { AccountRow, DetailRow, EmptyState } from "./PreviewPrimitives";
import styles from "./ecosystem-preview.module.css";

export type ViewActions = {
  navigate: (view: PreviewView) => void; createAccount: () => void;
  openAccount: (account: SampleAccount) => void; limited: () => void;
  preferences: () => void; openRecent: (recent: RecentId) => void;
};
type ViewProps = { copy: PreviewCopy; state: PreviewState; actions: ViewActions };
type DetailViewProps = ViewProps & { inspector: ReactNode; selectedAccountId?: string };

function SectionHeading({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return <div className={styles.sectionHeading}><h2>{title}</h2>{action && onAction ? <button type="button" className={styles.textButton} onClick={onAction}>{action}<ChevronRight size={16} aria-hidden="true" /></button> : null}</div>;
}

export function HomeView({ copy, state, actions }: ViewProps) {
  if (state === "empty") return <EmptyState title={copy.homeEmpty} body={copy.homeEmptyBody} action={copy.addAccount} onAction={actions.createAccount}><Landmark size={30} strokeWidth={1.3} /></EmptyState>;
  return <div className={styles.homeLayout}>
      <section className={styles.position} aria-label={copy.recordedPosition}>
        <div className={styles.positionLabel}><span>{copy.recordedPosition}</span><span className={styles.currencyBadge}>DOP</span></div>
        <p className={styles.positionAmount}><span>RD$</span>{SAMPLE.position}</p>
        <p className={styles.positionBasis}>{copy.recordedBasis}</p>
        <dl className={styles.positionDetails}><DetailRow label={copy.cashAndBank}>DOP {SAMPLE.cashAndBank}</DetailRow><DetailRow label={copy.youOwe}>DOP {SAMPLE.owed}</DetailRow></dl>
        <p className={styles.fine}>{copy.recordedAsOf}</p>
      </section>
      <section className={`${styles.contextCard} ${styles.homeComingUp}`} data-testid="home-coming-up"><SectionHeading title={copy.comingUp} action={copy.plan} onAction={() => actions.navigate("plan")} /><p className={styles.fine}>{copy.comingUpNote}</p><Commitments copy={copy} onClick={actions.limited} limit={2} /></section>
      <section className={styles.homeAccounts}><SectionHeading title={copy.accounts} action={copy.viewAll} onAction={() => actions.navigate("accounts")} />
        {SAMPLE.accounts.slice(0, 3).map((account) => <AccountRow key={account.id} account={account} copy={copy} onClick={() => actions.openAccount(account)} />)}
      </section>
      <section className={styles.homeActivity}><SectionHeading title={copy.recentActivity} action={copy.viewAll} onAction={() => actions.navigate("search")} />
        {SAMPLE.activity.map((item) => <button className={styles.activityRow} onClick={actions.limited} key={item.id}>
          <span className={styles.smallIcon}>{item.id === "transfer" ? <ArrowLeftRight size={18} /> : item.id === "income" ? <ArrowDownLeft size={18} /> : <ArrowUpRight size={18} />}</span>
          <span className={styles.rowText}><strong>{copy[item.title]}</strong><small>{copy[item.account]} · {copy.yesterday}</small></span><span className={styles.amount}>{item.amount}</span>
        </button>)}<p className={styles.fine}>{copy.activityNote}</p>
      </section>
    <aside className={`${styles.contextColumn} ${styles.homeContext}`}>
      <section className={styles.contextCard}><div className={styles.eyebrow}>{copy.separateCurrencies}</div><p className={styles.secondaryAmount}>USD {SAMPLE.accounts[4].balance}</p><p className={styles.fine}>{copy.usdBasis}</p></section>
      <div className={styles.coverageNote}><CircleHelp size={18} aria-hidden="true" /><p>{copy.unknownBasis}</p></div>
      <button className={styles.primaryButton} onClick={actions.limited}><Plus size={18} />{copy.record}</button>
    </aside>
  </div>;
}

export function AccountsView({ copy, state, actions, inspector, selectedAccountId }: DetailViewProps) {
  if (state === "empty") return <EmptyState title={copy.accountsEmpty} body={copy.accountsEmptyBody} action={copy.addAccount} onAction={actions.createAccount}><Wallet size={30} strokeWidth={1.3} /></EmptyState>;
  return <div className={inspector ? styles.detailLayout : styles.twoColumns}>
    <section className={styles.primaryColumn}>
      <SectionHeading title={copy.accountCount} action={copy.manage} onAction={actions.limited} />
      <div className={styles.accountList}>{SAMPLE.accounts.map((account) => <AccountRow key={account.id} account={account} copy={copy} selected={selectedAccountId === account.id} onClick={() => actions.openAccount(account)} />)}</div>
      <button className={styles.primaryButton} onClick={actions.createAccount}><Plus size={18} />{copy.addAccount}</button>
    </section>
    {inspector ?? <aside className={styles.contextColumn}><section className={styles.contextCard}><Landmark size={24} strokeWidth={1.4} /><h2>{copy.accountCoverage}</h2><p>{copy.accountCoverageBody}</p><div className={styles.inlineNote}><LockKeyhole size={15} />{copy.private}</div><p className={styles.fine}>{copy.samplePrivacy}</p></section><p className={styles.fine}>{copy.separateCurrencies}. {copy.recordedAsOf}.</p></aside>}
  </div>;
}

function Commitments({ copy, onClick, limit }: { copy: PreviewCopy; onClick: () => void; limit?: number }) {
  return <div className={styles.commitments}>{SAMPLE.commitments.slice(0, limit).map((item) => <button className={styles.commitment} key={item.id} onClick={onClick}>
    <span className={styles.dateBadge}>{copy[item.date]}</span><span><strong>{copy[item.title]}</strong><span className={styles.commitmentAmount}>{item.amount}</span><small>{copy.planned}</small></span>
  </button>)}</div>;
}

export function PlanView({ copy, state, actions }: ViewProps) {
  const [tab, setTab] = useState<"overview" | "goals" | "budgets" | "debts">("overview");
  if (state === "empty") return <EmptyState title={copy.planEmpty} body={copy.planEmptyBody} action={copy.newPlan} onAction={actions.limited}><Target size={30} strokeWidth={1.3} /></EmptyState>;
  return <>
    <div className={styles.sectionTabs} role="group" aria-label={copy.planTabs}>{(["overview", "goals", "budgets", "debts"] as const).map((item) => <button key={item} aria-pressed={tab === item} onClick={() => setTab(item)}>{copy[item]}</button>)}</div>
    <div className={styles.twoColumns}>
      <div className={styles.primaryColumn}>
        {tab === "overview" ? <>
          <section className={styles.planReadout}><p className={styles.eyebrow}><CalendarDays size={15} />{copy.until}</p><h2>{copy.projection}</h2><p>{copy.projectionBody}</p><div className={styles.readoutRule} aria-hidden="true" /></section>
          <SectionHeading title={copy.commitments} /><Commitments copy={copy} onClick={actions.limited} />
        </> : <section className={styles.planCard}>
          <span className={styles.planIcon}>{tab === "goals" ? <Target size={30} strokeWidth={1.3} /> : tab === "budgets" ? <Wallet size={30} strokeWidth={1.3} /> : <Landmark size={30} strokeWidth={1.3} />}</span>
          <h2>{copy[tab === "goals" ? "goalTitle" : tab === "budgets" ? "budgetTitle" : "debtTitle"]}</h2>
          <p>{copy[tab === "goals" ? "goalBody" : tab === "budgets" ? "budgetBody" : "debtBody"]}</p>
          <dl className={styles.details}>
            <DetailRow label={copy[tab === "goals" ? "goalRecorded" : tab === "budgets" ? "budgetRecorded" : "balanceOwed"]}>{tab === "goals" ? SAMPLE.plan.goalRecorded : tab === "budgets" ? SAMPLE.plan.budgetRecorded : `DOP ${SAMPLE.accounts[3].balance}`}</DetailRow>
            <DetailRow label={copy[tab === "goals" ? "goalTarget" : tab === "budgets" ? "budgetLimit" : "nextPayment"]}>{tab === "goals" ? SAMPLE.plan.goalTarget : tab === "budgets" ? SAMPLE.plan.budgetLimit : SAMPLE.commitments[0].amount}</DetailRow>
          </dl>{tab === "goals" || tab === "budgets" ? <p className={styles.noticeBox}>{tab === "goals" ? copy.goalCaveat : copy.budgetCaveat}</p> : null}<button className={styles.secondaryButton} onClick={actions.limited}>{copy.review}</button>
        </section>}
      </div>
      <aside className={styles.contextColumn}><section className={styles.contextCard}><h2>{copy.planBasis}</h2><p>{copy.planBasisBody}</p><p className={styles.fine}>{copy.recordedAsOf}</p></section><button className={styles.primaryButton} onClick={actions.limited}><Plus size={18} />{copy.newPlan}</button></aside>
    </div>
  </>;
}

export type SearchCategory = "all" | "accounts" | "activity" | "conversations" | "plans";
export function SearchView({ copy, state, actions, inspector, selectedAccountId, accountFilter, clearAccountFilter, query, setQuery, category, setCategory }: DetailViewProps & { accountFilter: SampleAccount | null; clearAccountFilter: () => void; query: string; setQuery: (query: string) => void; category: SearchCategory; setCategory: (category: SearchCategory) => void }) {
  const records: { id: string; title: CopyKey; category: typeof category; detail: string; open: () => void; accountId?: string }[] = [
    ...SAMPLE.accounts.map((account) => ({ id: account.id, title: account.name, category: "accounts" as const, detail: `${copy[account.type]} · ${account.currency}`, open: () => actions.openAccount(account), accountId: account.id })),
    ...SAMPLE.activity.map((item) => ({ id: `activity-${item.id}`, title: item.title, category: "activity" as const, detail: `${copy[item.account]} · ${item.amount}`, open: actions.limited, accountId: item.account })),
    ...RECENTS.map((recent) => ({ id: recent, title: recent, category: "conversations" as const, detail: copy.recentSample, open: () => actions.openRecent(recent) })),
    { id: "goal", title: "goalTitle", category: "plans", detail: copy.goalBody, open: () => actions.navigate("plan") },
  ];
  const filtered = records.filter((record) => (category === "all" || record.category === category) && (!accountFilter || record.accountId === accountFilter.id) && `${copy[record.title]} ${record.detail}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  if (state === "empty") return <EmptyState title={copy.searchEmpty} body={copy.searchEmptyBody}><Search size={30} strokeWidth={1.3} /></EmptyState>;
  return <div className={inspector ? styles.detailLayout : undefined}><div className={styles.searchCanvas}>
    <label className={styles.searchField}><Search size={21} aria-hidden="true" /><input type="search" aria-label={copy.searchLabel} placeholder={copy.searchPlaceholder} value={query} onChange={(event) => setQuery(event.target.value)} /></label>
    <div className={styles.filterRow} role="group" aria-label={copy.searchCategories}>{(["all", "accounts", "activity", "conversations", "plans"] as const).map((item) => <button key={item} className={styles.filterChip} aria-pressed={category === item} onClick={() => setCategory(item)}>{copy[item]}</button>)}</div>
    {accountFilter ? <button className={styles.filterChip} onClick={clearAccountFilter} aria-label={copy.clearFilter}>{copy[accountFilter.name]} ×</button> : null}
    <div className={styles.sectionHeading}><p className={styles.eyebrow}>{copy.sampleResults}</p>{query || category !== "all" || accountFilter ? <button className={styles.textButton} onClick={() => { setQuery(""); setCategory("all"); clearAccountFilter(); }}>{copy.clearSearch}</button> : null}</div>
    {filtered.length ? filtered.map((record) => <button key={record.id} className={styles.searchResult} onClick={record.open} data-preview-account={record.category === "accounts" ? record.id : undefined} aria-pressed={record.category === "accounts" ? selectedAccountId === record.id : undefined}><span className={styles.smallIcon}>{record.category === "accounts" ? <Wallet size={20} /> : record.category === "plans" ? <Target size={20} /> : <FileText size={20} />}</span><span className={styles.rowText}><strong>{copy[record.title]}</strong><small>{record.detail}</small></span><span className={styles.resultCategory}>{copy[record.category]}</span><ChevronRight size={16} aria-hidden="true" /></button>) : <EmptyState title={copy.noResults} body={copy.noResultsBody} />}
  </div>{inspector}</div>;
}

export function UpdatesView({ copy, state, actions }: ViewProps) {
  if (state === "empty") return <EmptyState title={copy.updatesEmpty} body={copy.updatesEmptyBody}><Check size={30} strokeWidth={1.3} /></EmptyState>;
  return <div className={styles.updatesList}>
    <UpdateRow title={copy.updateBalance} body={copy.updateBalanceBody} source={copy.everyday} action={copy.review} onClick={() => actions.openAccount(SAMPLE.accounts[0])}><CircleHelp size={21} /></UpdateRow>
    <UpdateRow title={copy.updatePayment} body={copy.updatePaymentBody} source={copy.plan} action={copy.openPlan} onClick={() => actions.navigate("plan")}><CalendarDays size={21} /></UpdateRow>
    <UpdateRow title={copy.updateImport} body={copy.updateImportBody} source={copy.localOnly} action={copy.review} onClick={actions.limited}><FileText size={21} /></UpdateRow>
  </div>;
}

function UpdateRow({ title, body, source, action, onClick, children }: { title: string; body: string; source: string; action: string; onClick: () => void; children: React.ReactNode }) {
  return <article className={styles.updateRow}><span className={styles.smallIcon}>{children}</span><div><p className={styles.eyebrow}>{source}</p><h2>{title}</h2><p>{body}</p><button className={styles.textButton} onClick={onClick}>{action}<ChevronRight size={16} /></button></div></article>;
}

export function SettingsView({ copy, actions }: ViewProps) {
  const groups: { title: CopyKey; rows: { title: CopyKey; body: CopyKey; icon: typeof UserRound; action: () => void }[] }[] = [
    { title: "app", rows: [{ title: "preferences", body: "preferencesBody", icon: SlidersHorizontal, action: actions.preferences }, { title: "personalization", body: "personalizationBody", icon: Settings2, action: actions.limited }, { title: "notifications", body: "notificationsBody", icon: Bell, action: actions.limited }] },
    { title: "account", rows: [{ title: "security", body: "securityBody", icon: ShieldCheck, action: actions.limited }, { title: "dataPrivacy", body: "dataControlsBody", icon: LockKeyhole, action: actions.limited }, { title: "usage", body: "usageBody", icon: Globe2, action: actions.limited }] },
    { title: "support", rows: [{ title: "help", body: "helpBody", icon: CircleHelp, action: actions.limited }] },
  ];
  return <div className={styles.settingsCanvas}>
    <button className={styles.profileRow} onClick={actions.limited}><span className={styles.avatar}><UserRound size={28} strokeWidth={1.4} /></span><span className={styles.rowText}><strong>{copy.personalDetails}</strong><small>{copy.personalDetailsBody}</small></span><ChevronRight size={18} /></button>
    <p className={styles.fine}>{copy.profileSample}</p>
    {groups.map((group) => <section key={group.title} className={styles.settingsGroup}><h2 className={styles.eyebrow}>{copy[group.title]}</h2><div>{group.rows.map((row) => <button key={row.title} className={styles.settingsRow} onClick={row.action}><row.icon size={20} strokeWidth={1.5} /><span className={styles.rowText}><strong>{copy[row.title]}</strong><small>{copy[row.body]}</small></span><ChevronRight size={17} /></button>)}</div></section>)}
  </div>;
}
