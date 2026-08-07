"use client";

import { useCallback, useId, useRef } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useModalSurface } from "../layout/useModalSurface";

/**
 * Account deletion request, lifted out of the profile menu.
 *
 * It portals to the body, outside the menu it opens from, so the menu's focus
 * trap never contained it and system back dismissed the menu or the drawer
 * underneath instead of this dialog. Owning its own registration is the only
 * way a portaled `aria-modal` surface gets that right.
 */

export type DeleteRequestState = "idle" | "submitting" | "success" | "error";

export default function ProfileDeleteRequestDialog({
  state,
  supportMailto,
  onClose,
  onSubmit,
}: {
  state: DeleteRequestState;
  supportMailto: string;
  onClose: () => void;
  onSubmit: () => void | Promise<void>;
}) {
  const { t } = useTranslation();
  const overlayId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  // A submission in flight owns the dialog until it settles. This is answered
  // before the history entry is spent, not inside onDismiss, so a refused press
  // leaves the entry intact and back still works once the request lands.
  const canDismiss = useCallback(() => state !== "submitting", [state]);

  useModalSurface({
    isOpen: true,
    overlayId,
    // The panel, not the full-screen wrapper. The wrapper's first focusable
    // child is the transparent backdrop, so trapping there opened keyboard
    // users on an undisclosed control where Enter dismissed the dialog.
    containerRef: panelRef,
    onDismiss: onClose,
    canDismiss,
    // Routed to the topmost layer, so opening this from a submenu no longer
    // depends on some other component happening to answer for it.
    onEscape: () => {
      if (canDismiss()) onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/25 p-4 backdrop-blur-sm dark:bg-black/60">
      <button
        tabIndex={-1}
        className="absolute inset-0"
        onClick={() => {
          if (state !== "submitting") {
            onClose();
          }
        }}
        aria-label={t(
          "settings.profile.request_deletion.close",
          "Close deletion request",
        )}
      />
      <div
        ref={panelRef}
        className="relative w-full max-w-sm rounded-[18px] border border-black/5 bg-white p-5 dark:border-white/10 dark:bg-[#1b1d20]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="argus-delete-request-title"
      >
        <div className="mb-3 flex items-center justify-between">
          <h3
            id="argus-delete-request-title"
            className="font-display text-[16px] font-medium text-black dark:text-white"
          >
            {t(
              "settings.profile.request_deletion.title",
              "Request account deletion",
            )}
          </h3>
          <button
            type="button"
            onClick={() => onClose()}
            disabled={state === "submitting"}
            className="rounded-full p-1.5 hover:bg-black/5 disabled:cursor-wait disabled:opacity-50 dark:hover:bg-white/10"
            aria-label={t(
              "settings.profile.request_deletion.close",
              "Close deletion request",
            )}
          >
            <X className="h-4 w-4 text-black/50 dark:text-white/50" />
          </button>
        </div>

        {state === "success" ? (
          <>
            <p className="text-[13px] leading-relaxed text-black/55 dark:text-white/55">
              {t(
                "settings.profile.request_deletion.success",
                "Request sent. We'll follow up by email.",
              )}
            </p>
            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => onClose()}
                className="rounded-md bg-black px-3 py-2 text-[13px] font-medium text-white hover:bg-black/85 dark:bg-white dark:text-black dark:hover:bg-white/85"
              >
                {t("common.done", "Done")}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="text-[13px] leading-relaxed text-black/55 dark:text-white/55">
              {t(
                "settings.profile.request_deletion.body",
                "Support handles account deletion. We'll verify ownership, process your account data, and follow up by email. Completed deletions cannot be undone.",
              )}
            </p>
            {state === "error" && (
              <p className="mt-3 text-[12px] leading-relaxed text-[#d66d75]">
                {t(
                  "settings.profile.request_deletion.error",
                  "We could not submit that request yet.",
                )}{" "}
                <a className="underline" href={supportMailto}>
                  {t(
                    "settings.profile.request_deletion.email_fallback",
                    "Email support",
                  )}
                </a>
              </p>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => onClose()}
                disabled={state === "submitting"}
                className="rounded-md px-3 py-2 text-[13px] font-medium text-black/55 hover:bg-black/5 disabled:cursor-wait disabled:opacity-50 dark:text-white/55 dark:hover:bg-white/10"
              >
                {t("common.cancel", "Cancel")}
              </button>
              <button
                type="button"
                onClick={() => void onSubmit()}
                disabled={state === "submitting"}
                className="rounded-md bg-[#d66d75]/12 px-3 py-2 text-[13px] font-medium text-[#b94c55] hover:bg-[#d66d75]/18 disabled:cursor-wait disabled:opacity-60 dark:text-[#e7a2a8]"
              >
                {state === "submitting"
                  ? t(
                      "settings.profile.request_deletion.submitting",
                      "Sending...",
                    )
                  : t(
                      "settings.profile.request_deletion.contact_support",
                      "Contact support",
                    )}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
