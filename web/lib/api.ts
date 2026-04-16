/**
 * Argus API Client
 *
 * This file consolidates hand-written network helpers with
 * auto-generated types from the backend FastAPI schema.
 */

import {
  UserResponse as GeneratedUserResponse,
  BacktestRequest,
  SimulationLogEntry,
  GetHistoryResponse as PaginatedHistory,
  SsoRequest,
  SsoResponse,
  BacktestResponse,
} from "./api/types.gen";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Core network helper for making authenticated requests to the Argus API.
 */
export async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  // Try to get auth token from localStorage if in browser environment
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;

  const headers = new Headers({
    "Content-Type": "application/json",
    ...(options.headers || {}),
  });

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = `API Error: ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) { // Validation error list
          errorMessage = (errorData.detail as { msg: string }[]).map((e) => e.msg).join(', ');
        }
      }
    } catch (e) {
      console.error(`Failed to parse error JSON from ${response.status} response`, e);
    }
    throw new Error(errorMessage);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

/* ==========================================================================
   AUTO-GENERATED TYPES (from @hey-api/openapi-ts)
   ========================================================================== */

export type UserResponse = GeneratedUserResponse;
export type HistoryResponse = PaginatedHistory;
export type { BacktestRequest, SimulationLogEntry, SsoRequest, SsoResponse, BacktestResponse };

/* ==========================================================================
   MANUALLY MAINTAINED TYPES (Internal Simulation Data Structures)
   ========================================================================== */

export interface Trade {
  entry_time: string;
  symbol: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  pnl_pct: number;
}

export interface BacktestMetrics {
  total_return_pct: number;
  sharpe_ratio: number;
  alpha: number;
  beta: number;
  calmar_ratio: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  avg_trade_duration: string;
  total_trades: number;
  sortino_ratio: number;
}

export interface BacktestResultData {
  metrics: BacktestMetrics;
  equity_curve: { value: number }[];
  benchmark_equity_curve: { value: number }[];
  trades: Trade[];
}

export interface SimulationData {
  result: BacktestResultData;
  strategies: { name: string };
}
