export async function refreshCanonicalMutation({
  refresh,
  onFailure,
}: {
  refresh: () => Promise<void>;
  onFailure: () => void;
}): Promise<void> {
  try {
    await refresh();
  } catch (error) {
    onFailure();
    throw error;
  }
}
