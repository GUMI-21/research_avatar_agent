import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const now = "2026-09-10T08:00:00Z";
const agent = {
  id: "agent-1",
  client_id: "local-demo",
  name: "Personal",
  system_prompt: "帮助我整理项目。",
  runtime: "native",
  model: "gpt-5.6-luna",
  knowledge_source_ids: [],
  created_at: now,
  updated_at: now,
};
const session = {
  id: "session-1",
  client_id: "local-demo",
  agent_id: agent.id,
  title: "项目计划",
  created_at: now,
  updated_at: now,
};

const run = {
  id: "run-1",
  session_id: session.id,
  agent_id: agent.id,
  runtime: "native",
  provider: "openai",
  model: "gpt-5.6-luna",
  status: "completed",
  input_tokens: 120,
  output_tokens: 45,
  cache_read_tokens: 10,
  cache_write_tokens: 0,
  cost_usd: "0.001230",
  cost_status: "estimated",
  duration_ms: 680,
  time_to_first_token_ms: 120,
  error_type: null,
  created_at: now,
};
class FakeWebSocket {
  static OPEN = 1;
  static instances: FakeWebSocket[] = [];
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = FakeWebSocket.OPEN;
      this.onopen?.();
    });
  }

  send(data: string) { this.sent.push(data); }
  close() { this.readyState = 3; this.onclose?.(); }
  emit(frame: object) { this.onmessage?.({ data: JSON.stringify(frame) }); }
}

function jsonResponse(body: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: async () => body,
  } as Response);
}

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("Agent workspace resources", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === "/api/v1/llm/providers") {
        return jsonResponse({ providers: [
          { provider: "mock", display_name: "Mock", default_model: "mock-echo", allow_custom_model: false,
            models: [{ model: "mock-echo", display_name: "Mock Echo", config: { provider: "mock", model: "mock-echo" } }] },
          { provider: "openai", display_name: "OpenAI", default_model: "gpt-5.6-luna", allow_custom_model: true,
            models: [{ model: "gpt-5.6-luna", display_name: "GPT-5.6 Luna", config: { provider: "openai", model: "gpt-5.6-luna" } }] },
        ] });
      }
      if (path === "/api/v1/llm/config" && !init?.method) {
        return jsonResponse({ provider: "mock", model: "mock-echo", base_url: "mock://local",
          api_key_configured: false, api_key_source: "not_required" });
      }
      if (path === "/api/v1/llm/config" && init?.method === "POST") {
        return jsonResponse({ provider: "openai", model: "gpt-5.6-luna", base_url: "https://api.openai.com/v1",
          api_key_configured: true, api_key_source: "request" });
      }
      if (path === "/api/v1/usage/runs?limit=100") return jsonResponse({ runs: [run] });
      if (path === "/api/v1/usage/summary") {
        return jsonResponse({
          run_count: 1,
          failed_count: 0,
          unavailable_cost_count: 0,
          input_tokens: 120,
          output_tokens: 45,
          cache_read_tokens: 10,
          cache_write_tokens: 0,
          cost_usd: "0.001230",
          average_duration_ms: 680,
        });
      }
      if (path === "/api/v1/agents" && init?.method === "POST") {
        return jsonResponse({ ...agent, id: "agent-2", ...JSON.parse(String(init.body)) });
      }
      if (path === "/api/v1/agents") return jsonResponse({ agents: [agent] });
      if (path === "/api/v1/sessions" && init?.method === "POST") {
        return jsonResponse({ ...session, id: "session-2", title: "新会话" });
      }
      if (path === "/api/v1/sessions") return jsonResponse({ sessions: [session] });
      if (path.includes("session-2/messages")) return jsonResponse({ messages: [] });
      if (path.includes("/messages")) {
        return jsonResponse({
          messages: [{
            id: "message-1",
            client_id: "local-demo",
            session_id: session.id,
            agent_id: agent.id,
            run_id: "run-1",
            role: "assistant",
            content: "历史回答",
            sequence: 1,
            created_at: now,
          }],
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    }));
  });

  it("loads agents, sessions, and message history", async () => {
    renderApp();

    expect(await screen.findByRole("heading", { name: "项目计划" })).toBeInTheDocument();
    expect(await screen.findByText("历史回答")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "聊天记录" })).toHaveValue(session.id);
    expect(screen.getByText("帮助我整理项目。")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/agents",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-Client-ID": "local-demo" }),
      }),
    );
  });

  it("creates a session for the selected agent", async () => {
    renderApp();
    const newSessionButton = screen.getByRole("button", { name: "新建对话" });
    await waitFor(() => expect(newSessionButton).toBeEnabled());
    fireEvent.click(newSessionButton);
    fireEvent.change(screen.getByPlaceholderText("这次要完成什么？"), {
      target: { value: "新会话" },
    });
    fireEvent.click(screen.getByRole("button", { name: "开始对话" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/sessions",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ agent_id: agent.id, title: "新会话" }),
        }),
      );
    });
    expect(await screen.findByRole("heading", { name: "新会话" })).toBeInTheDocument();
  });

  it("sends a message and renders streamed run events", async () => {
    renderApp();
    const composer = screen.getByLabelText("消息");
    await waitFor(() => expect(composer).toBeEnabled());
    fireEvent.change(composer, { target: { value: "解释状态图" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    const socket = FakeWebSocket.instances[0];
    expect(JSON.parse(socket.sent[0])).toEqual({
      type: "send_message",
      session_id: session.id,
      content: "解释状态图",
    });
    act(() => {
      socket.emit({ type: "run_started", run_id: "run-2", sequence: 1, payload: {} });
      socket.emit({ type: "assistant_delta", run_id: "run-2", sequence: null, payload: { text: "这是流式回答" } });
      socket.emit({ type: "run_finished", run_id: "run-2", sequence: 2, payload: { duration_ms: 120 } });
    });

    expect(screen.getByText("解释状态图")).toBeInTheDocument();
    expect(screen.getByText("这是流式回答")).toBeInTheDocument();
    expect(screen.getAllByText("运行完成")).toHaveLength(2);
  });
  it("shows persisted run and usage details", async () => {
    renderApp();
    await screen.findByRole("heading", { name: "项目计划" });

    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(await screen.findByText("gpt-5.6-luna")).toBeInTheDocument();
    expect(screen.getByText("680 ms / 120 ms")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Usage" }));
    expect(screen.getByText("Workspace 总计")).toBeInTheDocument();
    expect(screen.getAllByText("120")).toHaveLength(2);
    expect(screen.getAllByText("$0.001230")).toHaveLength(2);
  });

  it("creates an Agent with the selected default model", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "创建 Agent" }));
    await screen.findByText(/Provider：mock/);
    fireEvent.change(screen.getByPlaceholderText("例如：Personal"), { target: { value: "Reviewer" } });
    fireEvent.change(screen.getByPlaceholderText("说明 Agent 的职责和行为边界"), { target: { value: "Review code." } });
    fireEvent.click(screen.getByRole("button", { name: "创建" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/v1/agents",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "Reviewer", system_prompt: "Review code.", runtime: "native", model: "mock-echo" }),
      }),
    ));
  });
  it("configures the real server runtime from settings", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "设置" }));

    const provider = await screen.findByLabelText("Provider");
    await screen.findByText(/当前配置：mock \/ mock-echo/);
    fireEvent.change(provider, { target: { value: "openai" } });
    fireEvent.change(screen.getByLabelText("API Key（留空则使用 Server 环境变量）"), {
      target: { value: "test-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: "应用配置" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/v1/llm/config",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ provider: "openai", model: "gpt-5.6-luna", api_key: "test-key" }),
      }),
    ));
    expect(await screen.findByText(/当前配置：openai \/ gpt-5.6-luna/)).toBeInTheDocument();
  });
});
