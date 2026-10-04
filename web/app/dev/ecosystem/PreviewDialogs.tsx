"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronRight, Globe2, MessageSquare, Monitor, Search } from "lucide-react";
import AdaptivePanel from "@/components/ui/AdaptivePanel";
import AppearanceModal from "@/components/settings/AppearanceModal";
import LanguageModal from "@/components/settings/LanguageModal";
import { navigateFromOverlay } from "@/lib/overlay-history";
import { RECENTS, type PreviewCopy, type PreviewState, type RecentId } from "./preview-content";
import styles from "./ecosystem-preview.module.css";

export type SimpleDialog = "registration" | "limited" | "temporary" | "preferences" | "appearance" | "language" | "recents" | "context";

export default function PreviewDialogs({ dialog, copy, state, onClose, onDialog, onRecent, onNewChat }: {
  dialog: SimpleDialog; copy: PreviewCopy; state: PreviewState;
  onClose: () => void; onDialog: (dialog: SimpleDialog) => void; onRecent: (recent: RecentId) => void;
  onNewChat: (draft?: string) => void;
}) {
  const [query, setQuery] = useState("");
  const matches = state === "empty" ? [] : RECENTS.filter((recent) => copy[recent].toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  if (dialog === "appearance") return <AppearanceModal onClose={() => onDialog("preferences")} onBack={() => onDialog("preferences")} backLabel={copy.backPreferences} />;
  if (dialog === "language") return <LanguageModal onClose={() => onDialog("preferences")} onBack={() => onDialog("preferences")} backLabel={copy.backPreferences} />;
  const title = dialog === "registration" ? copy.registration : dialog === "temporary" ? copy.temporaryTitle : dialog === "preferences" ? copy.preferences : dialog === "recents" ? copy.recents : dialog === "context" ? copy.spaces : copy.limitedTitle;
  return <AdaptivePanel title={title} closeLabel={copy.close} onClose={onClose} width={dialog === "recents" ? "md" : "sm"}>
    <div className={styles.panel}>
      {dialog === "registration" ? <><p className={styles.bodyCopy}>{copy.registrationBody}</p><div className={styles.buttonStack}><Link href="/?auth=signup" prefetch={false} className={styles.primaryButton} onNavigate={(event) => { event.preventDefault(); navigateFromOverlay("/?auth=signup", onClose); }}>{copy.createAccount}</Link><Link href="/?auth=login" prefetch={false} className={styles.secondaryButton} onNavigate={(event) => { event.preventDefault(); navigateFromOverlay("/?auth=login", onClose); }}>{copy.signIn}</Link></div><p className={styles.fine}>{copy.registrationNote}</p></> : null}
      {dialog === "limited" || dialog === "context" || dialog === "temporary" ? <>
        <p className={styles.bodyCopy}>{dialog === "temporary" ? copy.temporaryBody : dialog === "context" ? copy.contextNote : copy.limitedBody}</p>
        {dialog === "temporary" ? <p className={styles.noticeBox}>{copy.temporaryContext}</p> : null}
        <button className={styles.primaryButton} onClick={onClose}>{copy.dismiss}</button>
      </> : null}
      {dialog === "preferences" ? <><button className={styles.settingsRow} onClick={() => onDialog("appearance")}><Monitor size={20} /><span className={styles.rowText}><strong>{copy.appearance}</strong><small>{copy.appearanceBody}</small></span><ChevronRight size={16} /></button><button className={styles.settingsRow} onClick={() => onDialog("language")}><Globe2 size={20} /><span className={styles.rowText}><strong>{copy.language}</strong><small>{copy.languageBody}</small></span><ChevronRight size={16} /></button><p className={styles.fine}>{copy.browserPreferences}</p></> : null}
      {dialog === "recents" ? <>
        <label className={styles.searchField}><Search size={18} aria-hidden="true" /><input type="search" maxLength={4000} aria-label={copy.searchRecents} placeholder={copy.searchRecents} value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <p className={styles.fine}>{copy.recentSample}</p>
        {matches.length ? matches.map((recent) => <button key={recent} className={styles.recentRow} onClick={() => onRecent(recent)}><MessageSquare size={20} strokeWidth={1.5} /><span>{copy[recent]}</span><ChevronRight size={16} /></button>) : <p className={styles.emptyRecents}>{query.trim() ? copy.recentsNoResults : copy.recentsEmpty}</p>}
        {!matches.length && query.trim() ? <p className={styles.fine}>{copy.searchDraftNote}</p> : null}
        <button className={styles.secondaryButton} onClick={() => onNewChat(!matches.length ? query.trim() : undefined)}>{copy.newChat}</button>
      </> : null}
    </div>
  </AdaptivePanel>;
}
