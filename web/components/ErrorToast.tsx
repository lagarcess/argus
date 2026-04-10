import { toast } from "sonner";
import { AlertCircle } from "lucide-react";

export interface ApiContractError {
  error: string;
  message: string;
  details?: Record<string, unknown>;
}

export const showErrorToast = (err: ApiContractError | unknown) => {
  // Catch standardized API contract errors
  if (err && typeof err === 'object' && 'error' in err && 'message' in err) {
    const e = err as ApiContractError;
    toast(e.error, {
      description: e.message,
      icon: <AlertCircle className="text-red-400" />,
      className: "bg-slate-900 border border-red-500/30 text-slate-100",
      action: {
        label: "Copy Details",
        onClick: () => navigator.clipboard.writeText(JSON.stringify(e.details || {}))
      }
    });
    return;
  }

  // Fallback for network crashes or weird payloads
  toast("UNKNOWN_ERROR", {
    description: err instanceof Error ? err.message : "A critical system error occurred.",
    icon: <AlertCircle className="text-red-400" />,
    className: "bg-slate-900 border border-red-500/30 text-slate-100",
  });
};
