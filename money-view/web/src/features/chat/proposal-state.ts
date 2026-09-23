export function canConfirmCanonicalProposal(editing: boolean, awaitingRevision: number | null, missingFieldCount: number) {
  return !editing && awaitingRevision === null && missingFieldCount === 0;
}
