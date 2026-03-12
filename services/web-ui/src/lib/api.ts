/**
 * API client for communicating with the Trading Automata backend.
 * All frontend-to-backend communication goes through this module.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include", // Send cookies (refresh token)
  });

  if (response.status === 401) {
    // Try refresh
    const refreshed = await refreshToken();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${accessToken}`;
      const retryResponse = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
        credentials: "include",
      });
      if (!retryResponse.ok) {
        throw new ApiError(retryResponse.status, await retryResponse.text());
      }
      return retryResponse.json();
    }
    throw new ApiError(401, "Session expired");
  }

  if (!response.ok) {
    const body = await response.text();
    let message: string;
    try {
      message = JSON.parse(body).detail || body;
    } catch {
      message = body;
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

async function refreshToken(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) return false;
    const data = await response.json();
    accessToken = data.access_token;
    return true;
  } catch {
    return false;
  }
}

// ---- Auth ----

export async function login(username: string, password: string) {
  const data = await request<{ access_token: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  accessToken = data.access_token;
  return data;
}

export async function changePassword(currentPassword: string, newPassword: string) {
  return request("/api/auth/password", {
    method: "PUT",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

// ---- Users ----

export interface User {
  id: number;
  username: string;
  email: string | null;
  role: string;
  is_active: boolean;
}

export async function getMe(): Promise<User> {
  return request("/api/users/me");
}

export async function listUsers(): Promise<User[]> {
  return request("/api/users/");
}

export async function createUser(data: { username: string; password: string; email?: string; role?: string }) {
  return request<User>("/api/users/", { method: "POST", body: JSON.stringify(data) });
}

export async function updateUser(userId: number, data: { email?: string; is_active?: boolean; role?: string }) {
  return request<User>(`/api/users/${userId}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteUser(userId: number) {
  return request(`/api/users/${userId}`, { method: "DELETE" });
}

// ---- Trades ----

export interface Trade {
  id: number;
  symbol: string;
  strategy: string;
  broker: string;
  bot_name: string | null;
  entry_price: number;
  entry_quantity: number;
  entry_timestamp: string | null;
  exit_price: number | null;
  exit_timestamp: string | null;
  gross_pnl: number | null;
  net_pnl: number | null;
  pnl_percent: number | null;
  is_winning_trade: boolean | null;
}

export async function listTrades(params?: {
  symbol?: string;
  strategy?: string;
  bot_name?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}): Promise<Trade[]> {
  const query = new URLSearchParams();
  if (params?.symbol) query.set("symbol", params.symbol);
  if (params?.strategy) query.set("strategy", params.strategy);
  if (params?.bot_name) query.set("bot_name", params.bot_name);
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  return request(`/api/trades${qs ? `?${qs}` : ""}`);
}

export async function exportTradesCsv(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<void> {
  const query = new URLSearchParams();
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  const qs = query.toString();
  const headers: Record<string, string> = {};
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  const res = await fetch(`${API_BASE}/api/trades/export${qs ? `?${qs}` : ""}`, {
    headers, credentials: "include",
  });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "trades.csv";
  a.click();
  URL.revokeObjectURL(url);
}

// ---- Positions ----

export interface Position {
  id: number;
  symbol: string;
  strategy: string;
  broker: string;
  bot_name: string | null;
  quantity: number;
  entry_price: number;
  current_price: number | null;
  is_open: boolean;
  unrealized_pnl: number | null;
}

export async function listPositions(isOpen?: boolean): Promise<Position[]> {
  const query = isOpen !== undefined ? `?is_open=${isOpen}` : "";
  return request(`/api/positions${query}`);
}

// ---- Bots ----

export interface TakeProfitTarget {
  pct: number;
  quantity_pct: number;
}

export interface BotConfig {
  id: number;
  name: string;
  strategy_id: string;
  credential_id: number;
  broker_type: string;
  environment: string;
  allocation: number;
  fence_type: string;
  fence_overage_pct: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  max_position_size: number;
  poll_interval_minutes: number;
  trailing_stop: boolean;
  trailing_stop_pct: number;
  trailing_activation_pct: number;
  take_profit_targets: TakeProfitTarget[] | null;
  is_active: boolean;
}

export async function listBots(): Promise<BotConfig[]> {
  return request("/api/bots/");
}

export async function createBot(data: {
  name: string;
  strategy_id: string;
  credential_id: number;
  allocation: number;
  fence_type?: string;
  fence_overage_pct?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  max_position_size?: number;
  poll_interval_minutes?: number;
}) {
  return request<BotConfig>("/api/bots/", { method: "POST", body: JSON.stringify(data) });
}

export async function deleteBot(botId: number) {
  return request(`/api/bots/${botId}`, { method: "DELETE" });
}

export async function cloneBot(botId: number): Promise<BotConfig> {
  return request(`/api/bots/${botId}/clone`, { method: "POST" });
}

export async function getBotStatus(): Promise<Record<string, unknown>> {
  return request("/api/bots/status/all");
}

export interface AccountPosition {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  currency: string;
  bot_name?: string;
}

export interface AccountSnapshot {
  broker_type: string;
  currency: string;
  equity: number;
  cash: number;
  positions: AccountPosition[];
  bot_name?: string;
  updated_at?: string;
}

export interface AccountsSummary {
  total_equity: number;
  total_cash: number;
  currency: string;
  accounts: AccountSnapshot[];
  positions: AccountPosition[];
}

export async function getAccountSnapshots(): Promise<AccountsSummary> {
  return request("/api/bots/accounts");
}

export async function getEngineHealth(): Promise<{ connected: boolean; status: string }> {
  return request("/api/bots/engine/health");
}

export interface BotEvent {
  type: "signal_generated" | "trade_executed" | "cycle_complete" | "error" | "bot_status_changed";
  timestamp: string;
  data: Record<string, any>;
}

export async function getBotEvents(botId: number, limit = 50): Promise<BotEvent[]> {
  return request(`/api/bots/${botId}/events?limit=${limit}`);
}

export interface BotStats {
  total_trades: number;
  total_pnl: number;
  winning_trades: number;
  win_rate: number;
  best_trade: number;
  worst_trade: number;
  avg_pnl_percent: number;
  equity?: number;
  cash?: number;
  equity_curve: EquityCurvePoint[];
  avg_holding_time_seconds?: number;
  max_drawdown_pct?: number;
  current_drawdown_pct?: number;
  benchmark?: {
    allocation: number;
    roi_pct: number;
    days_active: number;
    annualized_return_pct: number;
  };
}

export async function getBotStats(botId: number): Promise<BotStats> {
  return request(`/api/bots/${botId}/stats`);
}

export interface BacktestParams {
  strategy_id: string;
  symbol: string;
  days?: number;
  initial_capital?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  trailing_stop?: boolean;
}

export interface BacktestResult {
  strategy: string;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_capital: number;
  total_return_pct: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  best_trade_pct: number;
  worst_trade_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number | null;
  equity_curve: { date: string; equity: number }[];
}

export async function runBacktest(params: BacktestParams): Promise<BacktestResult> {
  return request("/api/bots/backtest", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export interface PortfolioHistoryPoint {
  date: string;
  equity: number;
  cash: number;
}

export async function getPortfolioHistory(days = 90): Promise<PortfolioHistoryPoint[]> {
  return request(`/api/bots/portfolio/history?days=${days}`);
}

// ---- Per-Bot Portfolio History ----

export interface PerBotHistoryPoint {
  date: string;
  bot_name: string;
  equity: number;
}

export async function getPerBotPortfolioHistory(days = 90): Promise<PerBotHistoryPoint[]> {
  return request(`/api/bots/portfolio/history/by-bot?days=${days}`);
}

// ---- Drawdown ----

export interface DrawdownStats {
  bot_name: string;
  max_drawdown_pct: number;
  current_drawdown_pct: number;
  high_water_mark: number;
}

export async function getDrawdownStats(): Promise<DrawdownStats[]> {
  return request("/api/bots/drawdown");
}

// ---- Trade Duration ----

export interface DurationStat {
  bot_name: string;
  avg_holding_seconds: number;
  trade_count: number;
}

export async function getTradeDurationStats(): Promise<DurationStat[]> {
  return request("/api/trades/duration-stats");
}

export function getWebSocketUrl(): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/api/ws?token=${accessToken}`;
}

export async function startBot(botId: number) {
  return request(`/api/bots/${botId}/start`, { method: "POST" });
}

export async function pauseBot(botId: number) {
  return request(`/api/bots/${botId}/pause`, { method: "POST" });
}

export async function resumeBot(botId: number) {
  return request(`/api/bots/${botId}/resume`, { method: "POST" });
}

export async function stopBot(botId: number) {
  return request(`/api/bots/${botId}/stop`, { method: "POST" });
}

// ---- Strategies ----

export interface StrategyStats {
  total_trades: number;
  winning_trades: number;
  win_rate: number | null;
  total_pnl: number;
  active_positions: number;
  popularity_rank: number;
}

export interface Strategy {
  id: string;
  class_name: string;
  name: string;
  short_description: string;
  description: string;
  category: string;
  risk_level: string;
  target_win_rate: number;
  recommended_timeframe: string;
  indicators: string[];
  asset_classes: string[];
  long_only: boolean;
  series?: string;
  stats: StrategyStats;
}

export async function listStrategies(): Promise<Strategy[]> {
  return request("/api/strategies/");
}

export async function getStrategy(strategyId: string): Promise<Strategy> {
  return request(`/api/strategies/${strategyId}`);
}

// ---- Portfolio ----

export interface PortfolioAllocation {
  symbol: string;
  value: number;
  unrealized_pnl: number;
  positions: number;
}

export interface PortfolioStrategyBreakdown {
  strategy: string;
  value: number;
  positions: number;
}

export interface PortfolioSummary {
  open_positions: number;
  total_invested: number;
  total_unrealized_pnl: number;
  allocations: PortfolioAllocation[];
  by_strategy: PortfolioStrategyBreakdown[];
  recent_pnl: number[];
}

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  return request("/api/portfolio/summary");
}

export interface EquityCurvePoint {
  date: string;
  daily_pnl: number;
  cumulative_pnl: number;
  trade_count: number;
}

export async function getEquityCurve(days?: number): Promise<EquityCurvePoint[]> {
  const qs = days ? `?days=${days}` : "";
  return request(`/api/portfolio/equity-curve${qs}`);
}

// ---- Analytics ----

export interface StrategyAnalytics {
  strategy: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl_percent: number;
  best_trade: number;
  worst_trade: number;
}

export interface SymbolAnalytics {
  symbol: string;
  total_trades: number;
  win_rate: number;
  total_pnl: number;
}

export interface TradeSummary {
  total_trades: number;
  total_pnl: number;
  winning_trades: number;
  win_rate: number;
}

export interface Analytics {
  summary: TradeSummary;
  by_strategy: StrategyAnalytics[];
  by_symbol: SymbolAnalytics[];
  equity_curve: EquityCurvePoint[];
}

export async function getAnalytics(params?: { date_from?: string; date_to?: string }): Promise<Analytics> {
  const query = new URLSearchParams();
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  const qs = query.toString();
  return request(`/api/analytics${qs ? `?${qs}` : ""}`);
}

// ---- Broker Credentials ----

export interface BrokerCredential {
  id: number;
  broker_type: string;
  environment: string;
  label: string;
  api_key_masked: string;
}

export async function listCredentials(): Promise<BrokerCredential[]> {
  return request("/api/broker-credentials/");
}

export async function createCredential(data: {
  broker_type: string;
  environment: string;
  api_key: string;
  secret_key: string;
  passphrase?: string;
  label: string;
}) {
  return request<BrokerCredential>("/api/broker-credentials/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCredential(
  credentialId: number,
  data: { api_key?: string; secret_key?: string; passphrase?: string; label?: string },
) {
  return request<BrokerCredential>(`/api/broker-credentials/${credentialId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteCredential(credentialId: number) {
  return request(`/api/broker-credentials/${credentialId}`, { method: "DELETE" });
}

// ---- Notifications ----

export interface NotificationPrefs {
  notify_trade_executed: boolean;
  notify_bot_error: boolean;
  notify_bot_stopped: boolean;
}

export async function getNotificationPrefs(): Promise<NotificationPrefs> {
  return request("/api/notifications/preferences");
}

export async function updateNotificationPref(key: string, enabled: boolean) {
  return request("/api/notifications/preferences", {
    method: "PUT",
    body: JSON.stringify({ key, enabled }),
  });
}

export async function getNotificationStatus(): Promise<{ smtp_configured: boolean }> {
  return request("/api/notifications/status");
}

// ---- Health ----

export async function healthCheck() {
  return request<{ status: string; service: string }>("/api/health");
}
