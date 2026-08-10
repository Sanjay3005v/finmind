// Typed shapes mirroring docs/API_CONTRACTS.md. The backend is being built
// concurrently and may not implement every field yet — keep these
// permissive (optional fields) rather than fighting drift.

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id?: string;
  };
}

export type RiskTolerance = "conservative" | "moderate" | "aggressive";
export interface UserProfile {
  user_id: string;
  full_name?: string | null;
  risk_tolerance: RiskTolerance;
  investment_horizon_years?: number | null;
  base_currency: string;
  created_at?: string;
  updated_at?: string;
}

export interface UpdateMeInput {
  full_name?: string;
  risk_tolerance?: RiskTolerance;
  investment_horizon_years?: number;
  base_currency?: string;
}

export interface Portfolio {
  id: string;
  user_id: string;
  name: string;
  base_currency: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreatePortfolioInput {
  name: string;
  base_currency: string;
  is_default?: boolean;
}

export interface Holding {
  id: string;
  portfolio_id: string;
  broker_connection_id?: string | null;
  symbol: string;
  exchange: string;
  asset_class?: string;
  sector?: string;
  quantity: number;
  avg_price: number;
  current_price?: number | null;
  currency: string;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
  updated_at?: string;
}

export type AssetClass = "equity" | "etf" | "mutual_fund" | "bond" | "cash" | "commodity" | "crypto";

export const ASSET_CLASSES: AssetClass[] = [
  "equity",
  "etf",
  "mutual_fund",
  "bond",
  "cash",
  "commodity",
  "crypto",
];

export interface CreateHoldingInput {
  symbol: string;
  exchange?: string;
  quantity: number;
  avg_price: number;
  current_price?: number;
  asset_class: AssetClass;
  sector?: string;
  currency?: string;
}

export interface MoverItem {
  symbol: string;
  asset_class: string;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
}

export interface MoversResponse {
  portfolio_id: string;
  gainers: MoverItem[];
  losers: MoverItem[];
}

export type PriceHistoryRange = "5d" | "1mo" | "3mo" | "6mo" | "1y" | "5y";

export interface PriceHistoryPoint {
  date: string;
  close: number;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  volume?: number | null;
}

export interface PriceHistoryResponse {
  symbol: string;
  exchange: string;
  ticker: string;
  currency: string;
  points: PriceHistoryPoint[];
}

export interface PriceRefreshFailure {
  symbol: string;
  exchange: string;
  error: string;
}

export interface PriceRefreshResponse {
  portfolio_id: string;
  updated: Holding[];
  failed: PriceRefreshFailure[];
}

export interface Transaction {
  id: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  fees?: number;
  executed_at: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}

export type PerformanceRange = "1M" | "3M" | "1Y" | "ALL";

export interface PerformanceResponse {
  portfolio_id: string;
  range: PerformanceRange;
  start_value: number;
  end_value: number;
  // All null (not just absent) when the portfolio has too little transaction
  // history to compute them yet — e.g. a fresh broker-synced portfolio with
  // no equity_curve. Render "—", never a fabricated 0.
  simple_return: number | null;
  cagr: number | null;
  annualized_volatility: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown: number | null;
  equity_curve: number[];
}

export interface AllocationSlice {
  label: string;
  value: number;
  percent?: number;
}

export interface AllocationBucket {
  market_value: Record<string, number>;
  percentage: Record<string, number>;
}

export interface AllocationResponse {
  portfolio_id: string;
  total_market_value: number;
  by_asset_class: AllocationBucket;
  by_sector: AllocationBucket;
  concentration_score: number;
}

export function allocationBucketToSlices(bucket: AllocationBucket): AllocationSlice[] {
  return Object.entries(bucket.market_value).map(([label, value]) => ({
    label,
    value,
    percent: bucket.percentage[label],
  }));
}

export type BrokerName = "dhan" | "angelone" | "upstox" | "fyers";
export type BrokerConnectionStatus = "connected" | "disconnected" | "error";
export type BrokerMode = "paper" | "live";

export interface BrokerConnection {
  id: string;
  broker: BrokerName;
  mode: BrokerMode;
  status: BrokerConnectionStatus;
  created_at?: string;
  last_synced_at?: string | null;
}

export interface CreateBrokerConnectionInput {
  broker: BrokerName;
  mode: BrokerMode;
}

export interface BrokerConnectionSyncResponse {
  connection_id: string;
  holdings_synced: number;
  last_synced_at: string | null;
}

export type DocumentStatus = "pending" | "processing" | "ready" | "failed";
export type DocumentSourceType = "filing" | "report" | "news" | "manual_upload";

export interface DocumentItem {
  id: string;
  title: string;
  source_type: DocumentSourceType;
  status: DocumentStatus;
  uploaded_at: string;
}

export interface ResearchCitation {
  chunk_id: string;
  document_title: string;
  snippet: string;
}

export interface ResearchQueryResponse {
  answer: string;
  citations: ResearchCitation[];
}

export interface AgentSession {
  id: string;
  title?: string | null;
  portfolio_id?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface CreateAgentSessionInput {
  portfolio_id?: string;
  title?: string;
}

export type AgentMessageRole = "user" | "assistant" | "system";

export interface AgentToolCall {
  name: string;
  args: Record<string, unknown>;
  result?: unknown;
}

export interface AgentMessage {
  id: string;
  role: AgentMessageRole;
  content: string;
  created_at: string;
  citations?: ResearchCitation[];
  tool_calls?: AgentToolCall[];
  // Not persisted on the message row itself (the backend only records it on
  // the `trade_approvals` table) — populated locally only for the message
  // created during the live stream that received the `interrupt` event, so
  // it survives this session but not a page reload. A still-pending
  // approval always remains visible on /trade-approvals independently.
  trade_approval_id?: string | null;
}

// Matches DATABASE_SCHEMA.sql's full check constraint. In practice the
// decision endpoint moves "approved" straight to "executed" synchronously
// (see app/api/v1/trade_approvals.py) — "approved" as a resting state and
// "expired" (no expiry job exists yet) are included for type-safety against
// the schema, not because the UI currently produces them.
export type TradeApprovalStatus = "pending" | "approved" | "rejected" | "expired" | "executed" | "failed";
export type TradeSide = "buy" | "sell";

export interface TradeApproval {
  id: string;
  symbol: string;
  side: TradeSide;
  quantity: number;
  status: TradeApprovalStatus;
  reasoning?: string;
  created_at: string;
  decided_at?: string | null;
  note?: string | null;
}

export type TradeDecision = "approve" | "reject";

export interface TradeApprovalDecisionInput {
  decision: TradeDecision;
  note?: string;
}

export interface ReportSummary {
  portfolio_id: string;
  generated_at: string;
  performance: PerformanceResponse;
  allocation: AllocationResponse;
}

export type ReportJobStatus = "queued" | "running" | "ready" | "error";

export interface ReportJob {
  job_id: string;
  status: ReportJobStatus;
  download_url?: string | null;
  created_at: string;
}
