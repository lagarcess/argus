export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

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

/** API types based on Argus Python schemas */
export interface BacktestRequest {
  strategy_name: string;
  symbols: string[];
  asset_class?: "crypto" | "equity";
  timeframe?: string;
  start_date?: string | null;
  end_date?: string | null;
  entry_patterns?: string[];
  exit_patterns?: string[];
  confluence_mode?: "OR" | "AND";
  slippage?: number;
  fees?: number;
  rsi_period?: number | null;
  rsi_oversold?: number;
  rsi_overbought?: number;
  ema_period?: number | null;
  benchmark_symbol?: string;
}

export interface SimulationLogEntry {
  id: string;
  strategy_name: string;
  symbols: string[];
  timeframe: string;
  status: "pending" | "completed" | "failed" | "processing";
  total_return_pct?: number;
  sharpe_ratio?: number;
  max_drawdown_pct?: number;
  win_rate_pct?: number;
  total_trades?: number;
  alpha?: number;
  beta?: number;
  calmar_ratio?: number;
  avg_trade_duration?: string;
  created_at: string;
  completed_at?: string;
}

export interface HistoryResponse {
  simulations: SimulationLogEntry[];
  total: number;
  next_cursor?: string | null;
}

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

export interface BacktestResponse {
  simulation_id: string | null;
  result: Record<string, unknown>; // Mapped from Python BacktestResult dict
}
