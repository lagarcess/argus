export function attentionAfterTurnSettled(
  currentIds: Iterable<string>,
  settledConversationId: string | null | undefined,
  activeConversationId: string | null | undefined,
) {
  const next = new Set(currentIds);
  const settled = settledConversationId?.trim();
  if (!settled) {
    return next;
  }
  if (settled !== activeConversationId?.trim()) {
    next.add(settled);
  }
  return next;
}

export function attentionAfterConversationOpen(
  currentIds: Iterable<string>,
  openedConversationId: string | null | undefined,
) {
  const next = new Set(currentIds);
  const opened = openedConversationId?.trim();
  if (opened) {
    next.delete(opened);
  }
  return next;
}
