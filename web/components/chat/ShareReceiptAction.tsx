"use client";

import { useState } from "react";
import { Check, Copy, Link2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  RECEIPT_OWNER_NOTE_MAX_LENGTH,
  copyReceiptLink,
  createEvidenceReceipt,
  receiptFailureReason,
  receiptUrl,
  type EvidenceReceipt,
} from "@/lib/evidence-receipts";

type ShareReceiptActionProps = {
  evidenceArtifactId: string;
};

type Phase = "idle" | "composing" | "creating" | "created";

const OUTLINE_BUTTON =
  "inline-flex min-h-9 items-center gap-1.5 rounded-full border border-black/10 px-3 py-1.5 text-[12px] font-medium text-[#505a63] transition-colors hover:bg-black/[0.03] dark:border-white/10 dark:text-[#8d969e] dark:hover:bg-white/[0.05]";
const SOLID_BUTTON =
  "inline-flex min-h-9 items-center gap-1.5 rounded-full bg-[#191c1f] px-3.5 py-1.5 text-[12px] font-medium text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-55 dark:bg-white dark:text-[#191c1f] dark:hover:bg-white/90";

/**
 * Owner-side share affordance on a completed result.
 *
 * The link is anonymous, not indexable, and revocable. The note is the only free
 * text a receipt carries, so it is bounded and its reach is stated before the
 * owner types into it rather than after.
 */
export default function ShareReceiptAction({
  evidenceArtifactId,
}: ShareReceiptActionProps) {
  const { t } = useTranslation();
  const [phase, setPhase] = useState<Phase>("idle");
  const [note, setNote] = useState("");
  const [receipt, setReceipt] = useState<EvidenceReceipt | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setPhase("creating");
    setError(null);
    try {
      const created = await createEvidenceReceipt(
        evidenceArtifactId,
        note.trim() || null,
      );
      setReceipt(created);
      setPhase("created");
    } catch (failure) {
      const reason = receiptFailureReason(failure);
      setError(
        reason === "note_rejected"
          ? t(
              "receipt.owner.errors.note_rejected",
              "That note cannot go public. Take out any keys or long codes.",
            )
          : reason === "rate_limited"
            ? t(
                "receipt.owner.errors.rate_limited",
                "You have made a lot of links just now. Try again shortly.",
              )
            : t(
                "receipt.owner.errors.create",
                "Argus could not make that link. Try again.",
              ),
      );
      setPhase("composing");
    }
  };

  if (phase === "created" && receipt) {
    const url = receiptUrl(receipt);
    return (
      <div className="mt-3 rounded-xl border border-black/[0.07] bg-black/[0.02] px-3.5 py-3 dark:border-white/[0.09] dark:bg-white/[0.03]">
        <div className="flex flex-wrap items-center gap-2">
          <code className="min-w-0 flex-1 truncate rounded-lg bg-black/[0.04] px-2 py-1.5 text-[12px] text-black/70 dark:bg-white/[0.06] dark:text-white/70">
            {url}
          </code>
          <button
            type="button"
            onClick={async () => {
              const ok = await copyReceiptLink(url);
              setCopied(ok);
              if (!ok) {
                setError(
                  t(
                    "receipt.owner.copy_failed",
                    "Copying did not work. Select the link and copy it.",
                  ),
                );
              }
            }}
            className={SOLID_BUTTON}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
            {copied
              ? t("receipt.owner.copied", "Copied")
              : t("receipt.owner.copy", "Copy link")}
          </button>
        </div>
        {error && (
          <p role="alert" className="mt-2 text-[12px] text-[#b94c55] dark:text-[#e7a2a8]">
            {error}
          </p>
        )}
        <p className="mt-2 text-[11.5px] leading-snug text-black/45 dark:text-white/45">
          {t(
            "receipt.owner.created_note",
            "Your name is not on it, search engines cannot find it, and you can take it down any time from Data Controls.",
          )}
        </p>
      </div>
    );
  }

  if (phase === "idle") {
    return (
      <div className="mt-3">
        <button
          type="button"
          onClick={() => setPhase("composing")}
          className={OUTLINE_BUTTON}
        >
          <Link2 className="h-3.5 w-3.5" />
          {t("receipt.owner.share", "Share this")}
        </button>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-xl border border-black/[0.07] bg-black/[0.02] px-3.5 py-3 dark:border-white/[0.09] dark:bg-white/[0.03]">
      <p className="text-[12.5px] leading-snug text-black/55 dark:text-white/55">
        {t(
          "receipt.owner.share_hint",
          "Makes a link anyone can open. It shows these numbers, locked as they are right now. Your chat, your name, and anything Argus remembers all stay out of it.",
        )}
      </p>
      <label
        htmlFor="receipt-owner-note"
        className="mt-3 block text-[12px] font-medium text-black/70 dark:text-white/70"
      >
        {t("receipt.owner.note_label", "Add a note if you want")}
      </label>
      <textarea
        id="receipt-owner-note"
        value={note}
        rows={2}
        maxLength={RECEIPT_OWNER_NOTE_MAX_LENGTH}
        onChange={(event) => setNote(event.target.value)}
        placeholder={t(
          "receipt.owner.note_placeholder",
          "Why is this worth a look?",
        )}
        className="mt-1.5 w-full resize-none rounded-lg border border-black/10 bg-white px-2.5 py-2 text-[13px] text-black outline-none focus-visible:ring-2 focus-visible:ring-black/15 dark:border-white/10 dark:bg-white/[0.04] dark:text-white dark:focus-visible:ring-white/20"
      />
      <p className="mt-1.5 text-[11.5px] leading-snug text-[#8a7530] dark:text-[#d3bb6a]">
        {t(
          "receipt.owner.note_public_warning",
          "Anyone with the link can read this. Keep it free of anything private.",
        )}
      </p>
      {error && (
        <p role="alert" className="mt-1.5 text-[12px] text-[#b94c55] dark:text-[#e7a2a8]">
          {error}
        </p>
      )}
      <div className="mt-2.5 flex justify-end gap-2">
        <button
          type="button"
          onClick={() => {
            setPhase("idle");
            setError(null);
          }}
          className={OUTLINE_BUTTON}
        >
          {t("receipt.owner.cancel", "Never mind")}
        </button>
        <button
          type="button"
          disabled={phase === "creating"}
          onClick={create}
          className={SOLID_BUTTON}
        >
          <Link2 className="h-3.5 w-3.5" />
          {phase === "creating"
            ? t("receipt.owner.creating", "Making the link...")
            : t("receipt.owner.create", "Make the link")}
        </button>
      </div>
    </div>
  );
}
