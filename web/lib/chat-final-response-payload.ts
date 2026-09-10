// Generated from FinalResponsePayload in agent_runtime/state/models.py.
// Run: poetry run python scripts/generate_chat_final_response_type.py
// Do not edit by hand; the backend model owns these fields.

import type { ToolResultCard } from "./tool-result-card";

export type ChatFinalResponsePayload = {
  tool_result_cards?: Array<ToolResultCard>;
  code?: string | null;
  result?: Record<string, unknown> | null;
  backtest_job?: Record<string, unknown> | null;
  error?: string | null;
  summary?: string | null;
  result_card?: Record<string, unknown> | null;
  explanation_context?: Record<string, unknown> | null;
};
