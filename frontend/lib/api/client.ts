import type {
  AgentMessage,
  AgentSession,
  AllocationResponse,
  ApiErrorBody,
  BrokerConnection,
  BrokerConnectionSyncResponse,
  CreateAgentSessionInput,
  CreateBrokerConnectionInput,
  CreateHoldingInput,
  CreatePortfolioInput,
  DocumentItem,
  DocumentSourceType,
  Holding,
  MoversResponse,
  Paginated,
  PerformanceRange,
  PerformanceResponse,
  Portfolio,
  PriceHistoryRange,
  PriceHistoryResponse,
  PriceRefreshResponse,
  ReportJob,
  ReportSummary,
  ResearchQueryResponse,
  TradeApproval,
  TradeApprovalDecisionInput,
  Transaction,
  UpdateMeInput,
  UserProfile,
} from "@/lib/api/types";

/**
 * Typed error thrown by every call in this module. Mirrors the backend's
 * `{ error: { code, message, request_id } }` envelope (API_CONTRACTS.md)
 * so callers/UI can branch on `code` and surface `message` directly.
 */
export class ApiError extends Error {
  code: string;
  status: number;
  requestId?: string;

  constructor(code: string, message: string, status: number, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

function getBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  accessToken?: string | null;
  body?: unknown;
}

async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { accessToken, body, headers, ...rest } = options;

  let response: Response;
  try {
    response = await fetch(`${getBaseUrl()}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch (cause) {
    throw new ApiError(
      "NETWORK_ERROR",
      cause instanceof Error
        ? `Could not reach the FINMIND API: ${cause.message}`
        : "Could not reach the FINMIND API.",
      0
    );
  }

  if (!response.ok) {
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      // Body wasn't JSON (e.g. an upstream 502 HTML page) — fall through.
    }

    if (
      parsed &&
      typeof parsed === "object" &&
      "error" in parsed &&
      typeof (parsed as ApiErrorBody).error?.message === "string"
    ) {
      const { code, message, request_id } = (parsed as ApiErrorBody).error;
      throw new ApiError(code || "UNKNOWN_ERROR", message, response.status, request_id);
    }

    throw new ApiError(
      "UNKNOWN_ERROR",
      `Request failed with status ${response.status}.`,
      response.status
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

// ---- Meta -----------------------------------------------------------------

export function getMe(accessToken: string | null) {
  return apiFetch<UserProfile>("/me", { accessToken });
}

export function updateMe(accessToken: string | null, input: UpdateMeInput) {
  return apiFetch<UserProfile>("/me", { method: "PATCH", accessToken, body: input });
}

// ---- Portfolios -------------------------------------------------------------

export function listPortfolios(accessToken: string | null) {
  return apiFetch<Portfolio[]>("/portfolios", { accessToken });
}

export function createPortfolio(accessToken: string | null, input: CreatePortfolioInput) {
  return apiFetch<Portfolio>("/portfolios", { method: "POST", accessToken, body: input });
}

export function getPortfolio(accessToken: string | null, id: string) {
  return apiFetch<Portfolio>(`/portfolios/${id}`, { accessToken });
}

export function getHoldings(accessToken: string | null, portfolioId: string) {
  return apiFetch<Holding[]>(`/portfolios/${portfolioId}/holdings`, { accessToken });
}

export function createHolding(
  accessToken: string | null,
  portfolioId: string,
  input: CreateHoldingInput
) {
  return apiFetch<Holding>(`/portfolios/${portfolioId}/holdings`, {
    method: "POST",
    accessToken,
    body: input,
  });
}

export function deleteHolding(accessToken: string | null, portfolioId: string, holdingId: string) {
  return apiFetch<void>(`/portfolios/${portfolioId}/holdings/${holdingId}`, {
    method: "DELETE",
    accessToken,
  });
}

export function getMovers(accessToken: string | null, portfolioId: string, limit = 5) {
  return apiFetch<MoversResponse>(`/portfolios/${portfolioId}/movers?limit=${limit}`, { accessToken });
}

export function refreshHoldingPrices(accessToken: string | null, portfolioId: string) {
  return apiFetch<PriceRefreshResponse>(`/portfolios/${portfolioId}/holdings/refresh-prices`, {
    method: "POST",
    accessToken,
  });
}

export function getPriceHistory(
  accessToken: string | null,
  portfolioId: string,
  holdingId: string,
  range: PriceHistoryRange = "1mo"
) {
  return apiFetch<PriceHistoryResponse>(
    `/portfolios/${portfolioId}/holdings/${holdingId}/price-history?range=${range}`,
    { accessToken }
  );
}

export function getTransactions(accessToken: string | null, portfolioId: string) {
  return apiFetch<Paginated<Transaction>>(`/portfolios/${portfolioId}/transactions`, {
    accessToken,
  });
}

export function getPerformance(
  accessToken: string | null,
  portfolioId: string,
  range: PerformanceRange = "1M"
) {
  return apiFetch<PerformanceResponse>(
    `/portfolios/${portfolioId}/performance?range=${range}`,
    { accessToken }
  );
}

export function getAllocation(accessToken: string | null, portfolioId: string) {
  return apiFetch<AllocationResponse>(`/portfolios/${portfolioId}/allocation`, { accessToken });
}

// ---- Broker connections -----------------------------------------------------

export function listBrokerConnections(accessToken: string | null) {
  return apiFetch<BrokerConnection[]>("/broker-connections", { accessToken });
}

export function createBrokerConnection(
  accessToken: string | null,
  input: CreateBrokerConnectionInput
) {
  return apiFetch<BrokerConnection>("/broker-connections", {
    method: "POST",
    accessToken,
    body: input,
  });
}

export function disconnectBroker(accessToken: string | null, id: string) {
  return apiFetch<void>(`/broker-connections/${id}`, { method: "DELETE", accessToken });
}

export function syncBrokerConnection(accessToken: string | null, id: string) {
  // Runs synchronously on the backend for now (see broker_service.sync_holdings's
  // docstring) — returns the sync result directly rather than a job id.
  return apiFetch<BrokerConnectionSyncResponse>(`/broker-connections/${id}/sync`, {
    method: "POST",
    accessToken,
  });
}

// ---- Documents & research (RAG) ---------------------------------------------

export function listDocuments(accessToken: string | null) {
  return apiFetch<DocumentItem[]>("/documents", { accessToken });
}

export async function uploadDocument(
  accessToken: string | null,
  file: File,
  title: string,
  sourceType: DocumentSourceType = "manual_upload"
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);
  formData.append("source_type", sourceType);

  let response: Response;
  try {
    response = await fetch(`${getBaseUrl()}/documents`, {
      method: "POST",
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
      body: formData,
    });
  } catch (cause) {
    throw new ApiError(
      "NETWORK_ERROR",
      cause instanceof Error
        ? `Could not reach the FINMIND API: ${cause.message}`
        : "Could not reach the FINMIND API.",
      0
    );
  }

  if (!response.ok) {
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      // ignore non-JSON error bodies
    }
    if (
      parsed &&
      typeof parsed === "object" &&
      "error" in parsed &&
      typeof (parsed as ApiErrorBody).error?.message === "string"
    ) {
      const { code, message, request_id } = (parsed as ApiErrorBody).error;
      throw new ApiError(code || "UNKNOWN_ERROR", message, response.status, request_id);
    }
    throw new ApiError(
      "UNKNOWN_ERROR",
      `Upload failed with status ${response.status}.`,
      response.status
    );
  }

  return (await response.json()) as DocumentItem;
}

export function queryResearch(accessToken: string | null, query: string) {
  return apiFetch<ResearchQueryResponse>("/research/query", {
    method: "POST",
    accessToken,
    body: { query },
  });
}

// ---- Agents (LangGraph sessions) --------------------------------------------

export function listAgentSessions(accessToken: string | null) {
  return apiFetch<AgentSession[]>("/agents/sessions", { accessToken });
}

export function createAgentSession(accessToken: string | null, input: CreateAgentSessionInput = {}) {
  return apiFetch<AgentSession>("/agents/sessions", {
    method: "POST",
    accessToken,
    body: input,
  });
}

export function getAgentMessages(accessToken: string | null, sessionId: string) {
  return apiFetch<AgentMessage[]>(`/agents/sessions/${sessionId}/messages`, { accessToken });
}

// ---- Agent chat streaming (SSE) ----------------------------------------------
//
// The backend streams `token` / `tool_call` / `citation` / `interrupt` / `done`
// events per API_CONTRACTS.md's streaming event contract. `EventSource` can't
// be used directly (it only supports GET, no custom Authorization header), so
// this parses the `text/event-stream` body from a normal authenticated
// `fetch` POST by hand.

export type AgentStreamEventName = "token" | "tool_call" | "citation" | "interrupt" | "done";

export interface AgentStreamEvent {
  event: AgentStreamEventName;
  data: Record<string, unknown>;
}

async function streamSSE(
  path: string,
  accessToken: string | null,
  body: unknown,
  onEvent: (evt: AgentStreamEvent) => void
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${getBaseUrl()}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch (cause) {
    throw new ApiError(
      "NETWORK_ERROR",
      cause instanceof Error
        ? `Could not reach the FINMIND API: ${cause.message}`
        : "Could not reach the FINMIND API.",
      0
    );
  }

  if (!response.ok || !response.body) {
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      // Body wasn't JSON — fall through to the generic error below.
    }
    if (
      parsed &&
      typeof parsed === "object" &&
      "error" in parsed &&
      typeof (parsed as ApiErrorBody).error?.message === "string"
    ) {
      const { code, message, request_id } = (parsed as ApiErrorBody).error;
      throw new ApiError(code || "UNKNOWN_ERROR", message, response.status, request_id);
    }
    throw new ApiError("UNKNOWN_ERROR", `Request failed with status ${response.status}.`, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex: number;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);

      const lines = rawEvent.split("\n");
      const eventLine = lines.find((l) => l.startsWith("event:"));
      const dataLine = lines.find((l) => l.startsWith("data:"));
      if (!eventLine || !dataLine) continue;

      const eventName = eventLine.slice("event:".length).trim() as AgentStreamEventName;
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(dataLine.slice("data:".length).trim());
      } catch {
        // Malformed data line — skip rather than crash the whole stream.
        continue;
      }
      onEvent({ event: eventName, data });
    }
  }
}

export function streamAgentMessage(
  accessToken: string | null,
  sessionId: string,
  content: string,
  onEvent: (evt: AgentStreamEvent) => void
) {
  return streamSSE(`/agents/sessions/${sessionId}/messages`, accessToken, { content }, onEvent);
}

export function streamResumeSession(
  accessToken: string | null,
  sessionId: string,
  onEvent: (evt: AgentStreamEvent) => void
) {
  return streamSSE(`/agents/sessions/${sessionId}/resume`, accessToken, undefined, onEvent);
}

// ---- Trade approvals ---------------------------------------------------------

export function listTradeApprovals(accessToken: string | null, status?: string) {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiFetch<TradeApproval[]>(`/trade-approvals${qs}`, { accessToken });
}

export function getTradeApproval(accessToken: string | null, id: string) {
  return apiFetch<TradeApproval>(`/trade-approvals/${id}`, { accessToken });
}

export function decideTradeApproval(
  accessToken: string | null,
  id: string,
  input: TradeApprovalDecisionInput
) {
  return apiFetch<TradeApproval>(`/trade-approvals/${id}/decision`, {
    method: "POST",
    accessToken,
    body: input,
  });
}

// ---- Reports -------------------------------------------------------------

export function getReportSummary(accessToken: string | null, portfolioId: string) {
  return apiFetch<ReportSummary>(`/reports/${portfolioId}/summary`, { accessToken });
}

export function generateReport(accessToken: string | null, portfolioId: string) {
  return apiFetch<ReportJob>(`/reports/${portfolioId}/generate`, {
    method: "POST",
    accessToken,
  });
}

export function getReportJob(accessToken: string | null, jobId: string) {
  return apiFetch<ReportJob>(`/reports/jobs/${jobId}`, { accessToken });
}
