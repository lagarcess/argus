"use client";

import type { RefObject } from "react";
import { ArrowUp, Mic, Plus } from "lucide-react";
import EmptyChatGreeting from "@/components/chat/EmptyChatGreeting";
import StrategyConfirmationCard from "@/components/chat/StrategyConfirmationCard";
import { DCA_CONFIRMATION, type PreviewCopy, type RecentId } from "./preview-content";
import styles from "./ecosystem-preview.module.css";

export default function PreviewChat({ copy, draft, onDraft, recent, onNotice, onLimited, inputRef }: {
  copy: PreviewCopy; draft: string; onDraft: (draft: string) => void; recent: RecentId | null;
  onNotice: () => void; onLimited: () => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
}) {
  return <div className={styles.chatCanvas}>
    {recent ? <section className={styles.sampleTranscript}>
      <p className={styles.eyebrow}>{copy.recentSample}</p><h1>{copy[recent]}</h1><p>{copy.sampleConversationBody}</p>
      {recent === "recentInvest" ? <div className={styles.artifactExample}><h2 className={styles.eyebrow}>{copy.artifactTitle}</h2><StrategyConfirmationCard confirmation={DCA_CONFIRMATION} disabled /><p className={styles.fine}>{copy.artifactNote}</p></div> : null}
      <a href="/chat" className={styles.textButton}>{copy.existingChat}<span aria-hidden="true">↗</span></a>
      <p className={styles.fine}>{copy.registrationNote}</p>
    </section> : <section className={styles.chatColdStart} aria-label={copy.argus}>
      <h1 className="sr-only">{copy.argus}</h1>
      <EmptyChatGreeting isGuest />
      <div className={styles.starterChips} role="group" aria-label={copy.suggestions}>{(["chipMoney", "chipMarket", "chipAccounts"] as const).map((key) => <button key={key} className={styles.starterChip} onClick={() => { onDraft(copy[key]); inputRef.current?.focus(); }}>{copy[key]}</button>)}</div>
    </section>}
    <div className={styles.composerDock}>
      <form className={styles.composer} data-testid="preview-composer" onSubmit={(event) => { event.preventDefault(); onNotice(); }}>
        <textarea ref={inputRef} aria-label={copy.composerLabel} placeholder={copy.composerPlaceholder} value={draft} rows={2} maxLength={4000}
          data-testid="preview-composer-input" onChange={(event) => onDraft(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); onNotice(); } }} />
        <div className={styles.composerTools}><button type="button" className={styles.iconButton} aria-label={copy.attach} onClick={onLimited}><Plus size={22} strokeWidth={1.6} /></button>
          <span aria-hidden="true" className={styles.composerSpacer} /><button type="button" className={styles.iconButton} aria-label={copy.voice} onClick={onLimited}><Mic size={20} strokeWidth={1.6} /></button>
          <button type="submit" className={styles.sendButton} aria-label={copy.send} data-testid="preview-send"><ArrowUp size={20} /></button>
        </div>
      </form><p className={styles.composerHint}>{copy.composerHint}</p>
    </div>
  </div>;
}
