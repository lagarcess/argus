"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Check, Landmark, Plus } from "lucide-react";
import AdaptivePanel from "@/components/ui/AdaptivePanel";
import { inlineFailureTextClass } from "@/lib/failure-treatment";
import { ACCOUNT_TYPES, SAMPLE, type AccountType, type PreviewCopy, type SampleAccount } from "./preview-content";
import AccountDetail from "./AccountDetail";
import { AccountIcon, DetailRow } from "./PreviewPrimitives";
import styles from "./ecosystem-preview.module.css";

export type AccountPanel = { mode: "create" } | { mode: "detail" | "edit" | "correction"; account: SampleAccount };
type Screen = "detail" | "create" | "edit" | "draft" | "correction" | "adjustment";
type Draft = { type: AccountType | null; currency: string; nickname: string; balance: string; institution: string; reference: string };

// Syntax for this preview's displayed decimal format only. Keep the raw string:
// money precision, limits and posting belong to the future financial contract.
function isBalanceDraft(value: string): boolean {
  const text = value.trim();
  return text === "" || /^[+−-]?(?:(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?|\.\d+)$/.test(text);
}

export default function AccountPanels({ panel, copy, onClose, onActivity, onLimited }: {
  panel: AccountPanel; copy: PreviewCopy; onClose: () => void;
  onActivity: (account: SampleAccount) => void; onLimited: () => void;
}) {
  const account = panel.mode === "create" ? null : panel.account;
  const [screen, setScreen] = useState<Screen>(panel.mode);
  const [draftFrom, setDraftFrom] = useState<"create" | "edit">("create");
  const [showTypes, setShowTypes] = useState(panel.mode === "create");
  const [draft, setDraft] = useState<Draft>({
    type: account?.type ?? null, currency: account?.currency ?? "DOP",
    nickname: account ? copy[account.name] : "", balance: account?.balance ?? "", institution: "", reference: "",
  });
  const [note, setNote] = useState("");
  const [balanceValidationRequested, setBalanceValidationRequested] = useState(false);
  const invalidBalance = balanceValidationRequested && !isBalanceDraft(draft.balance);
  const fieldId = useId();
  const balanceInputRef = useRef<HTMLInputElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const typeRef = useRef<HTMLFieldSetElement>(null);
  const lastScreen = useRef(screen);
  const lastTypeDisplay = useRef(showTypes);
  useEffect(() => {
    if (lastScreen.current !== screen) contentRef.current?.focus();
    else if (lastTypeDisplay.current !== showTypes) typeRef.current?.focus();
    lastScreen.current = screen;
    lastTypeDisplay.current = showTypes;
  }, [screen, showTypes]);
  const editField = (key: keyof Draft, value: string) => setDraft((previous) => ({ ...previous, [key]: value }));
  const title = screen === "detail" ? (account ? copy[account.name] : copy.accountDetails)
    : screen === "create" ? copy.createTitle : screen === "edit" ? copy.editDetails
      : screen === "draft" ? copy.draftTitle : screen === "correction" ? copy.correctionTitle : copy.adjustmentTitle;
  const back = screen === "edit" || screen === "correction" ? () => { if (panel.mode === "detail") setScreen("detail"); else onClose(); }
    : screen === "draft" ? () => setScreen(draftFrom)
      : screen === "adjustment" ? () => setScreen("correction") : undefined;

  return <AdaptivePanel title={title} closeLabel={copy.close} onClose={onClose} width="lg"
    onBack={back} backLabel={screen === "draft" ? copy.returnDraft : copy.backAccount}>
    <div ref={contentRef} tabIndex={-1} aria-label={title} className={styles.panel} data-testid={screen === "create" ? "account-create" : screen === "edit" ? "account-edit" : screen === "correction" || screen === "adjustment" ? "correction-review" : screen === "draft" ? "account-draft" : undefined}>
      {screen !== "detail" ? <p className={styles.eyebrow}>{copy.localOnly}</p> : null}
      {screen === "detail" && account ? <AccountDetail account={account} copy={copy} onEdit={() => { setShowTypes(false); setScreen("edit"); }} onCorrection={() => setScreen("correction")} onActivity={onActivity} /> : null}

      {(screen === "create" || screen === "edit") ? <form onSubmit={(event) => {
        event.preventDefault();
        if (!draft.type) return;
        setBalanceValidationRequested(true);
        if (!isBalanceDraft(draft.balance)) {
          balanceInputRef.current?.focus();
          return;
        }
        setDraft((previous) => ({ ...previous, balance: previous.balance.trim() }));
        setDraftFrom(screen);
        setScreen("draft");
      }}>
        <p className={styles.intro}>{screen === "create" ? copy.createIntro : copy.draftOnly}</p>
        <fieldset ref={typeRef} tabIndex={-1} className={styles.fieldset}>
          <legend className={styles.fieldLabel}>{copy.chooseType}</legend>
          {showTypes ? <div className={styles.typeGrid}>{ACCOUNT_TYPES.map((type) => <button type="button" key={type} className={styles.typeChoice} aria-pressed={draft.type === type} onClick={() => { setDraft((previous) => ({ ...previous, type })); setShowTypes(false); }}>
            <AccountIcon type={type} /><span>{copy[type]}</span>{draft.type === type ? <Check size={16} /> : null}
          </button>)}</div> : <div className={styles.selectedType}>
            {draft.type ? <AccountIcon type={draft.type} /> : <Landmark size={20} />}
            <strong>{draft.type ? copy[draft.type] : copy.type}</strong>
            <button className={styles.textButton} type="button" onClick={() => setShowTypes(true)}>{copy.change}</button>
          </div>}
        </fieldset>
        {draft.type ? <>
          <label className={styles.field} htmlFor={`${fieldId}-currency`}><span>{copy.currency}</span>
            <select id={`${fieldId}-currency`} value={draft.currency} onChange={(event) => editField("currency", event.target.value)}><option value="DOP">{copy.dopCurrency}</option><option value="USD">{copy.usdCurrency}</option></select>
          </label>
          <label className={styles.field} htmlFor={`${fieldId}-nickname`}><span>{copy.nickname}</span>
            <input id={`${fieldId}-nickname`} value={draft.nickname} maxLength={120} autoComplete="off" onChange={(event) => editField("nickname", event.target.value)} />
          </label>
          <label className={styles.field} htmlFor={`${fieldId}-balance`}><span>{copy.startingBalance}</span>
            <div className={styles.amountInput}><span>{draft.currency}</span><input ref={balanceInputRef} id={`${fieldId}-balance`} type="text" inputMode="decimal" value={draft.balance} maxLength={30} autoComplete="off" aria-invalid={invalidBalance || undefined} aria-describedby={`${fieldId}-balance-hint${invalidBalance ? ` ${fieldId}-balance-error` : ""}`} onChange={(event) => editField("balance", event.target.value)} /></div>
            <small id={`${fieldId}-balance-hint`}>{copy.leaveBlank}</small>
            {invalidBalance ? <span id={`${fieldId}-balance-error`} role="alert" className={`text-xs ${inlineFailureTextClass}`}>{copy.invalidBalance}</span> : null}
          </label>
          {screen === "edit" ? <fieldset className={styles.fieldset}><legend className={styles.fieldLabel}>{copy.moreDetails}</legend>
            <label className={styles.field} htmlFor={`${fieldId}-institution`}><span>{copy.institution}</span><input id={`${fieldId}-institution`} value={draft.institution} maxLength={120} autoComplete="off" onChange={(event) => editField("institution", event.target.value)} /></label>
            <label className={styles.field} htmlFor={`${fieldId}-reference`}><span>{copy.reference}</span><input id={`${fieldId}-reference`} value={draft.reference} maxLength={40} autoComplete="off" onChange={(event) => editField("reference", event.target.value)} /></label>
          </fieldset> : null}
          <button className={`${styles.primaryButton} ${styles.fullWidth}`} type="submit">{copy.reviewDraft}</button>
        </> : null}
        <p className={styles.fine}>{copy.draftOnly}</p>
      </form> : null}

      {screen === "draft" ? <>
        <div className={styles.draftBadge}><Plus size={18} /><span>{copy.draftOnly}</span></div>
        <h3 className={styles.draftName}>{draft.nickname.trim() || copy.unnamed}</h3>
        <dl className={styles.details}>
          <DetailRow label={copy.type}>{draft.type ? copy[draft.type] : copy.notProvided}</DetailRow>
          <DetailRow label={copy.currency}>{draft.currency}</DetailRow>
          <DetailRow label={copy.startingBalance}>{draft.balance.trim() || copy.unknownBalance}</DetailRow>
          {draftFrom === "edit" ? <><DetailRow label={copy.institution}>{draft.institution.trim() || copy.notProvided}</DetailRow><DetailRow label={copy.reference}>{draft.reference.trim() || copy.notProvided}</DetailRow></> : null}
        </dl>
        <p className={styles.noticeBox} role="status">{copy.draftNotice}</p>
        <div className={styles.buttonRow}><button className={styles.secondaryButton} onClick={() => setScreen(draftFrom)}>{copy.returnDraft}</button><button className={styles.primaryButton} onClick={onClose}>{copy.done}</button></div>
      </> : null}

      {screen === "correction" || screen === "adjustment" ? <>
        <p className={styles.intro}>{copy.everyday} · DOP</p>
        <dl className={styles.details}>
          <DetailRow label={copy.checkedOn}>{copy.today}</DetailRow>
          <DetailRow label={copy.previousBalance}>DOP {SAMPLE.accounts[0].balance}</DetailRow>
          <DetailRow label={copy.observedBalance}>DOP {SAMPLE.correction.observed}</DetailRow>
          <DetailRow label={copy.difference}><strong>{SAMPLE.correction.difference}</strong></DetailRow>
        </dl>
        <p className={styles.fine}>{copy.correctionBasis}</p>
        <p className={styles.bodyCopy}>{copy.discrepancy}</p>
        <p className={styles.noticeBox}>{copy.incompleteHistory}</p>
        {screen === "correction" ? <>
          <label className={styles.field} htmlFor={`${fieldId}-note`}><span>{copy.notes}</span><textarea id={`${fieldId}-note`} value={note} maxLength={200} rows={3} onChange={(event) => setNote(event.target.value)} /><small>{copy.noteLimit} ({note.length}/200)</small></label>
          <div className={styles.buttonStack}><button className={styles.primaryButton} onClick={() => setScreen("adjustment")}>{copy.previewAdjustment}</button><button className={styles.textButton} onClick={onLimited}>{copy.missingActivity}</button></div>
        </> : <><p className={styles.noticeBox} role="status">{copy.adjustmentNotice}</p>{note ? <blockquote className={styles.noteQuote}>{note}</blockquote> : null}<button className={styles.primaryButton} onClick={onClose}>{copy.done}</button></>}
      </> : null}
    </div>
  </AdaptivePanel>;
}
