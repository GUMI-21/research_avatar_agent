import { getClientId } from "../clientIdentity";

export type WorkspaceIdentity = {
  username: string;
  created_at: string;
};

export type Agent = {
  id: string;
  client_id: string;
  name: string;
  system_prompt: string;
  runtime: string;
  model: string | null;
  knowledge_source_ids: string[];
  created_at: string;
  updated_at: string;
};

export type WorkspaceSession = {
  id: string;
  client_id: string;
  agent_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: string;
  client_id: string;
  session_id: string;
  agent_id: string;
  run_id: string | null;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  sequence: number;
  created_at: string;
};

export type RunUsage = {
  id: string;
  session_id: string;
  agent_id: string;
  runtime: string;
  provider: string | null;
  model: string | null;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  input_tokens: number | null;
  output_tokens: number | null;
  cache_read_tokens: number | null;
  cache_write_tokens: number | null;
  cost_usd: string | null;
  cost_status: string;
  duration_ms: number | null;
  time_to_first_token_ms: number | null;
  error_type: string | null;
  created_at: string;
};

export type UsageSummary = {
  run_count: number;
  failed_count: number;
  unavailable_cost_count: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cost_usd: string;
  average_duration_ms: number | null;
};


export type AgentMemory = {
  id: string;
  agent_id: string;
  content: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};
export type LLMModelOption = {
  model: string;
  display_name: string;
  config: { provider: string; model: string };
};

export type LLMProviderOption = {
  provider: string;
  display_name: string;
  default_model: string;
  allow_custom_model: boolean;
  models: LLMModelOption[];
};

export type LLMConfigResponse = {
  provider: string;
  model: string;
  base_url: string;
  api_key_configured: boolean;
  api_key_source: "request" | "environment" | "not_required";
};
class APIRequestError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit, scoped = true): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(scoped ? { "X-Client-ID": getClientId() } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new APIRequestError(
      response.status,
      body?.detail || `请求失败（${response.status}）`,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const workspaceApi = {
  ensureWorkspace: async (username: string) => {
    const normalized = username.trim().toLowerCase();
    try {
      return await request<WorkspaceIdentity>(
        `/api/v1/workspaces/${encodeURIComponent(normalized)}`, undefined, false,
      );
    } catch (error) {
      if (!(error instanceof APIRequestError) || error.status !== 404) throw error;
      return request<WorkspaceIdentity>("/api/v1/workspaces", {
        method: "POST",
        body: JSON.stringify({ username: normalized }),
      }, false);
    }
  },
  listAgents: async () =>
    (await request<{ agents: Agent[] }>("/api/v1/agents")).agents,
  createAgent: (input: { name: string; system_prompt: string; runtime?: string; model?: string }) =>
    request<Agent>("/api/v1/agents", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  listSessions: async () =>
    (await request<{ sessions: WorkspaceSession[] }>("/api/v1/sessions"))
      .sessions,
  createSession: (input: { agent_id: string; title: string }) =>
    request<WorkspaceSession>("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  listMessages: async (sessionId: string) =>
    (
      await request<{ messages: Message[] }>(
        `/api/v1/sessions/${encodeURIComponent(sessionId)}/messages?limit=50`,
      )
    ).messages,
  listMemories: async (agentId: string) =>
    (await request<{ memories: AgentMemory[] }>(
      `/api/v1/agents/${encodeURIComponent(agentId)}/memories`,
    )).memories,
  createMemory: (agentId: string, content: string) =>
    request<AgentMemory>(`/api/v1/agents/${encodeURIComponent(agentId)}/memories`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  updateMemory: (agentId: string, memoryId: string, enabled: boolean) =>
    request<AgentMemory>(
      `/api/v1/agents/${encodeURIComponent(agentId)}/memories/${encodeURIComponent(memoryId)}`,
      { method: "PATCH", body: JSON.stringify({ enabled }) },
    ),
  deleteMemory: (agentId: string, memoryId: string) =>
    request<void>(
      `/api/v1/agents/${encodeURIComponent(agentId)}/memories/${encodeURIComponent(memoryId)}`,
      { method: "DELETE" },
    ),
  listLLMProviders: async () =>
    (await request<{ providers: LLMProviderOption[] }>("/api/v1/llm/providers")).providers,
  getLLMConfig: () => request<LLMConfigResponse>("/api/v1/llm/config"),
  configureLLM: (input: { provider: string; model: string; api_key?: string }) =>
    request<LLMConfigResponse>("/api/v1/llm/config", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  listRuns: async () =>
    (await request<{ runs: RunUsage[] }>("/api/v1/usage/runs?limit=100")).runs,
  getUsageSummary: () => request<UsageSummary>("/api/v1/usage/summary"),
};
