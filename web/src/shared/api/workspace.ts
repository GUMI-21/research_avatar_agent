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

export const clientId = import.meta.env.VITE_CLIENT_ID?.trim() || "local-demo";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Client-ID": clientId,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(body?.detail || `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

export const workspaceApi = {
  listAgents: async () =>
    (await request<{ agents: Agent[] }>("/api/v1/agents")).agents,
  createAgent: (input: { name: string; system_prompt: string }) =>
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
};
