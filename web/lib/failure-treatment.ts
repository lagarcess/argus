/**
 * Shared visual source for every "this went wrong" treatment.
 *
 * One failure class = one treatment, consumed from here so surfaces cannot
 * drift apart again. Gates stay owned by callers: amber applies only where
 * `metadata.recovery.retryable === true` already decides it today.
 *
 * Tone map:
 * - Retryable interruption  -> amber notice (act on it, retry exists).
 * - Terminal failure        -> one warm failure red, split from the
 *   value-negative rose #d66d75 (lost money keeps the rose; broken keeps this).
 * - Degraded / unavailable  -> muted italic value, never a hero tone.
 * - Quiet non-retryable     -> neutral-bordered notice, no alarm, no retry.
 */

export const FAILURE_TERMINAL_LIGHT = "#b3593f";
export const FAILURE_TERMINAL_DARK = "#e08d70";

/** Small failure text under a control or list row (size stays local). */
export const inlineFailureTextClass = "text-[#b3593f] dark:text-[#e08d70]";

/** Canonical blocking-error banner (the AuthForm shape, tokenized). */
export const blockingErrorBannerClass =
  "rounded-[20px] border border-[#b3593f]/25 bg-[#b3593f]/[0.05] px-5 py-3 text-center text-sm font-medium text-[#9c4a33] dark:border-[#e08d70]/25 dark:bg-[#e08d70]/[0.06] dark:text-[#e5a48b]";

/** Status-pill fragments for terminal failure on artifact cards. */
export const terminalStatusToneClass =
  "border-[#b3593f]/30 bg-[#b3593f]/[0.08] text-[#9c4a33] dark:border-[#e08d70]/30 dark:bg-[#e08d70]/10 dark:text-[#e5a48b]";

/** Unavailable/degraded metric value: visibly absent, never a hero tone. */
export const degradedValueClass = "italic text-[#8d969e] dark:text-white/45";

// ── Retryable (amber) notice ────────────────────────────────────────────────
// Issue #313 landed as PR #318 at the ownership layer without touching this
// styling, so the amber family folds in here with the rest of the vocabulary.

export const retryableNoticeContainerClass =
  "flex w-full items-start gap-3 rounded-[14px] border border-amber-700/25 bg-amber-500/[0.06] px-4 py-3 dark:border-amber-300/20 dark:bg-amber-300/[0.06]";

export const retryableNoticeIconClass =
  "mt-0.5 h-4 w-4 shrink-0 text-amber-800/70 dark:text-amber-300/70";

export const retryableNoticeBodyClass =
  "min-w-0 flex-1 text-[15px] leading-[1.55] tracking-[0.2px] text-black/75 dark:text-white/75";

export const retryableNoticeRetryPillClass =
  "shrink-0 self-center rounded-full border border-amber-700/30 px-3 py-1.5 text-[13px] font-medium text-amber-900/80 transition-colors hover:bg-amber-500/10 dark:border-amber-300/30 dark:text-amber-200/90 dark:hover:bg-amber-300/10";

// ── Quiet (non-retryable) notice ────────────────────────────────────────────

export const quietNoticeContainerClass =
  "flex w-full items-start gap-3 rounded-[14px] border border-black/12 bg-black/[0.03] px-4 py-3 dark:border-white/12 dark:bg-white/[0.04]";

export const quietNoticeIconClass =
  "mt-0.5 h-4 w-4 shrink-0 text-black/50 dark:text-white/55";

export const quietNoticeBodyClass =
  "min-w-0 flex-1 text-[15px] leading-[1.55] tracking-[0.2px] text-black/75 dark:text-white/75";

// ── Panel-scale failure state (palette, composer discovery) ─────────────────

/** Icon marking an in-panel failure so error never reads as empty. */
export const panelFailureIconClass =
  "h-5 w-5 text-[#b3593f]/70 dark:text-[#e08d70]/70";
