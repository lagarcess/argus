"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { patchAuthProfileMutation, getAuthSessionQueryKey } from "@/lib/api/@tanstack/react-query.gen";
import { toast } from "sonner";

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { mutateAsync, isPending } = useMutation(patchAuthProfileMutation());

  const completeOnboarding = async (intent: string) => {
    try {
      await mutateAsync({
        body: {
          onboarding_completed: true,
          onboarding_step: "completed",
          onboarding_intent: intent,
        },
      });
      await queryClient.invalidateQueries({ queryKey: getAuthSessionQueryKey() });
      router.push(`/builder?intent=${encodeURIComponent(intent)}`);
    } catch {
      toast.error("Failed to complete onboarding", {
        description: "Please try again or contact support."
      });
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-12 space-y-6">
      <h1 className="text-3xl font-bold text-slate-100">Welcome to Argus</h1>
      <p className="text-slate-400">
        Pick your primary objective so we can prefill your first strategy draft.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: "Momentum", value: "momentum" },
          { label: "Mean Reversion", value: "mean_reversion" },
          { label: "Breakout", value: "breakout" },
        ].map((intent) => (
          <button
            key={intent.value}
            disabled={isPending}
            onClick={() => completeOnboarding(intent.value)}
            className="glass-card border border-slate-800 p-4 text-left hover:border-cyan-400/40"
          >
            <div className="text-slate-100 font-semibold">{intent.label}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
