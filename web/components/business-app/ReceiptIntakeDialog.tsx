"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, FileUp, ReceiptText } from "lucide-react";
import { useTranslation } from "react-i18next";
import AdaptivePanel from "@/components/ui/AdaptivePanel";
import {
  BUSINESS_RECEIPT_MAX_BYTES,
  BUSINESS_RECEIPT_MEDIA_TYPES,
  type ReceiptSummary,
} from "@/lib/business-api";
import { useBusiness } from "./BusinessWorkspace";
import { primaryButtonClass, secondaryButtonClass } from "./business-ui";
import { useInputCapabilities } from "./useInputCapabilities";

/** Where a captured receipt goes next: its review, or the composer. */
export type IntakeTarget = "inbox" | "composer";

const ACCEPT = BUSINESS_RECEIPT_MEDIA_TYPES.join(",");

type Rejection = "unsupported" | "too_large" | "heic";

function rejectionFor(file: File): Rejection | null {
  const type = file.type.toLowerCase();
  if (type === "image/heic" || type === "image/heif" || /\.hei[cf]$/i.test(file.name)) return "heic";
  if (!(BUSINESS_RECEIPT_MEDIA_TYPES as readonly string[]).includes(type)) return "unsupported";
  if (file.size > BUSINESS_RECEIPT_MAX_BYTES) return "too_large";
  return null;
}

export default function ReceiptIntakeDialog({
  target,
  onClose,
  onCaptured,
}: {
  target: IntakeTarget | null;
  onClose: () => void;
  onCaptured: (receipt: ReceiptSummary, target: IntakeTarget) => void;
}) {
  if (!target) return null;
  return <IntakeSurface target={target} onClose={onClose} onCaptured={onCaptured} />;
}

function IntakeSurface({
  target,
  onClose,
  onCaptured,
}: {
  target: IntakeTarget;
  onClose: () => void;
  onCaptured: (receipt: ReceiptSummary, target: IntakeTarget) => void;
}) {
  const { t, i18n } = useTranslation();
  const { source } = useBusiness();
  const capabilities = useInputCapabilities();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [rejection, setRejection] = useState<Rejection | null>(null);
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState<"idle" | "uploading" | "failed">("idle");
  const [dragging, setDragging] = useState(false);

  const choose = (candidate: File | null | undefined) => {
    if (!candidate) return;
    const reason = rejectionFor(candidate);
    setRejection(reason);
    setFile(reason ? null : candidate);
    setState("idle");
  };

  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const pasted = Array.from(event.clipboardData?.files ?? [])[0];
      if (pasted) {
        event.preventDefault();
        choose(pasted);
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, []);

  const save = async () => {
    if (!file) return;
    setState("uploading");
    try {
      const captured = await source.uploadReceipt(file, consent);
      onCaptured(captured, target);
    } catch {
      setState("failed");
    }
  };

  const sizeLabel = (bytes: number) =>
    new Intl.NumberFormat(i18n.resolvedLanguage ?? "en", { maximumFractionDigits: 1 }).format(bytes / 1024 / 1024);

  const rejectionText: Record<Rejection, string> = {
    unsupported: t("business.intake.unsupported", "This file type isn't supported. Use a PDF, JPG or PNG."),
    too_large: t("business.intake.too_large", "This file is larger than 10 MB. Use a smaller photo or PDF."),
    heic: t("business.intake.heic", "This is an iPhone HEIC photo. Upload it from your iPhone's browser, which converts it, or export it as JPG first."),
  };

  return (
    <AdaptivePanel
      title={t("business.intake.title", "Upload receipt")}
      closeLabel={t("common.close", "Close")}
      onClose={onClose}
      width="md"
      footer={
        <div className="flex justify-end gap-2 px-4 pb-4">
          <button type="button" className={secondaryButtonClass} onClick={onClose}>
            {t("common.cancel", "Cancel")}
          </button>
          <button
            type="button"
            className={primaryButtonClass}
            disabled={!file || state === "uploading"}
            onClick={() => void save()}
          >
            {state === "uploading"
              ? t("business.intake.saving", "Saving…")
              : t("business.intake.save", "Save to Inbox")}
          </button>
        </div>
      }
    >
      <div className="space-y-4 px-4 pb-2">
        <p className="text-[14px] text-black/60 dark:text-white/60">
          {t("business.intake.formats", "PDF, JPG or PNG, up to 10 MB. The original stays private to you.")}
        </p>

        <div
          onDragOver={(event) => {
            if (!capabilities.dropAndPaste) return;
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            if (!capabilities.dropAndPaste) return;
            event.preventDefault();
            setDragging(false);
            choose(event.dataTransfer.files[0]);
          }}
          className={`rounded-[16px] border border-dashed p-5 text-center transition-colors ${
            dragging ? "border-black/40 bg-black/[0.03] dark:border-white/40" : "border-black/15 dark:border-white/15"
          }`}
        >
          {file ? (
            <div className="flex items-center justify-center gap-2 text-[14px] font-medium text-black dark:text-white">
              <ReceiptText className="h-5 w-5 shrink-0" />
              <span className="truncate">{file.name}</span>
              <span className="shrink-0 font-normal text-black/50 dark:text-white/50">{`${sizeLabel(file.size)} MB`}</span>
            </div>
          ) : capabilities.dropAndPaste ? (
            <p className="text-[14px] text-black/55 dark:text-white/55">
              {t("business.intake.drop", "Drop a receipt here or paste an image.")}
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            <button type="button" className={secondaryButtonClass} onClick={() => fileInputRef.current?.click()}>
              <FileUp className="h-4 w-4" />
              {file ? t("business.intake.replace", "Choose another") : t("business.intake.choose", "Choose file")}
            </button>
            {capabilities.cameraCapture ? (
              <button type="button" className={secondaryButtonClass} onClick={() => cameraInputRef.current?.click()}>
                <Camera className="h-4 w-4" />
                {t("business.intake.camera", "Take photo")}
              </button>
            ) : null}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT}
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => {
              choose(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/jpeg,image/png"
            capture="environment"
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => {
              choose(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
        </div>

        {rejection ? (
          <p role="alert" className="text-[14px] text-[#a8434c] dark:text-[#ec9aa0]">{rejectionText[rejection]}</p>
        ) : null}
        {state === "failed" ? (
          <p role="alert" className="text-[14px] text-[#a8434c] dark:text-[#ec9aa0]">
            {t("business.intake.failed", "We couldn't save this receipt. Check your connection and try again. It won't be saved twice.")}
          </p>
        ) : null}

        <label className="flex items-start gap-3 rounded-[14px] bg-black/[0.03] p-3 text-[14px] text-black/75 dark:bg-white/[0.04] dark:text-white/75">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            className="mt-0.5 h-5 w-5 shrink-0 accent-black dark:accent-white"
          />
          <span>
            {t("business.intake.consent", "Prepare it with AI after saving. The receipt is sent to our AI provider to fill in the details for your review. Leave this off to fill them in yourself.")}
          </span>
        </label>
      </div>
    </AdaptivePanel>
  );
}
