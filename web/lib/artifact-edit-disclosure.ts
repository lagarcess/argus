import type { TFunction } from "i18next";

/** Requested edits that did not materialize, independent of artifact kind. */
export type ArtifactEditDisclosure = {
  unapplied: { op: string; target: string; reason: string }[];
  note?: string | null;
};

/** Materialized facts outrank planner prose; artifact adapters name targets. */
export function artifactEditDisclosureText(
  disclosure: ArtifactEditDisclosure | null | undefined,
  t: TFunction,
  unappliedTargetsText: (targets: string[]) => string,
): string | null {
  if (!disclosure) return null;
  if (disclosure.unapplied?.some((entry) => entry.reason === "no_change_applied")) {
    return t("chat.artifact_edit_disclosure.no_change_applied");
  }
  const targets = (disclosure.unapplied ?? [])
    .map((entry) => String(entry.target ?? "").trim())
    .filter(Boolean);
  if (targets.length > 0) return unappliedTargetsText(targets);
  return String(disclosure.note ?? "").trim() || null;
}
