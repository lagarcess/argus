// Generated from FinalResponsePayload in agent_runtime/state/models.py.
// Run: poetry run python scripts/generate_chat_final_response_type.py
// Do not edit by hand; the backend model owns these fields.

export type ChatFinalResponsePayload = {
  code?: string | null;
  result?: Record<string, unknown> | null;
  backtest_job?: Record<string, unknown> | null;
  error?: string | null;
  summary?: string | null;
  result_card?: Record<string, unknown> | null;
  explanation_context?: Record<string, unknown> | null;
};
