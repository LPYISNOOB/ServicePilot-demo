export type Evidence = {
  document_id: string;
  title: string;
  version: string;
  source: string;
  snippet: string;
  score: number;
  effective_date: string;
};

export type AgentResponse = {
  thread_id: string;
  ticket_id: string;
  status: "completed" | "pending_approval";
  answer: string;
  intent: string;
  risk_level: string;
  pending_approval: Record<string, unknown> | null;
  route_log: string[];
  evidence: Evidence[];
  action: Record<string, unknown>;
  action_result: Record<string, unknown>;
  errors: string[];
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function sendMessage(input: {
  message: string;
  customer_email: string;
  order_id: string;
  thread_id?: string;
}): Promise<AgentResponse> {
  return request("/api/v1/chat", { method: "POST", body: JSON.stringify(input) });
}

export function submitApproval(
  threadId: string,
  input: { approved: boolean; reviewer: string; comment: string },
): Promise<AgentResponse> {
  return request(`/api/v1/approvals/${encodeURIComponent(threadId)}`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

