export type DraftMutationInput<TPayload> = {
  strategyId: string | null;
  strategyPayload: TPayload;
  createStrategy: (args: { body: TPayload }) => Promise<unknown>;
  updateStrategy: (args: { path: { id: string }; body: TPayload }) => Promise<unknown>;
};

export type DraftSuccessHooks = {
  onSaved: (mode: "create" | "update") => void;
  onSuccessToast: () => void;
  onRedirectToStrategies: () => void;
};

export async function persistStrategyDraft<TPayload>(
  input: DraftMutationInput<TPayload>
): Promise<"create" | "update"> {
  if (input.strategyId) {
    await input.updateStrategy({
      path: { id: input.strategyId },
      body: input.strategyPayload,
    });
    return "update";
  }

  await input.createStrategy({ body: input.strategyPayload });
  return "create";
}

export async function saveDraftStrategy<TPayload>(
  input: DraftMutationInput<TPayload> & DraftSuccessHooks
): Promise<"create" | "update"> {
  const mode = await persistStrategyDraft(input);
  input.onSaved(mode);
  input.onSuccessToast();
  input.onRedirectToStrategies();
  return mode;
}
