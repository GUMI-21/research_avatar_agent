import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const now = "2026-09-10T08:00:00Z";
let demoMode = false;
const agent = {
  id: "agent-1",
  client_id: "local-demo",
  name: "Personal",
  avatar_emoji: "🧠",
  system_prompt: "帮助我整理项目。",
  runtime: "native",
  provider: "openai",
  model: "gpt-5.6-luna",
  workspace_path: null,
  knowledge_source_ids: [],
  skill_ids: [],
  created_at: now,
  updated_at: now,
};
const reviewer = {
  ...agent,
  id: "agent-2",
  name: "Reviewer",
  avatar_emoji: "🔎",
  system_prompt: "审查实现并指出风险。",
  runtime: "codex",
  provider: null,
  model: null,
  workspace_path: "server",
};
const session = {
  id: "session-1",
  client_id: "local-demo",
  agent_id: agent.id,
  title: "项目计划",
  created_at: now,
  updated_at: now,
};

const reviewerSession = {
  ...session,
  id: "session-review",
  agent_id: reviewer.id,
  title: "代码审查",
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
  skill_versions: [{ id: "daily-planning", version_hash: "abcdef1234567890" }],
  created_at: now,
};
const skill = {
  id: "daily-planning",
  name: "每日工作规划",
  description: "根据日程整理工作计划。",
  applicable_scenarios: ["每日规划"],
  recommended_tools: ["calendar_list_events"],
  version_hash: "abcdef1234567890",
};
const knowledgeSource = {
  id: "source-1",
  client_id: "local-demo",
  name: "Project Notes",
  source_type: "markdown",
  root_path: "D:\\Notes\\Project",
  sync_status: "ready",
  error_message: null,
  last_synced_at: now,
  created_at: now,
  updated_at: now,
};
const memory = {
  id: "memory-1",
  agent_id: agent.id,
  content: "回答时优先使用简洁中文",
  enabled: true,
  created_at: now,
  updated_at: now,
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
    demoMode = false;
    window.localStorage.clear();
    FakeWebSocket.instances = [];
    const registeredWorkspaces = new Set(["local-demo"]);
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const workspaceMatch = path.match(/^\/api\/v1\/workspaces\/([^/]+)$/);
      if (workspaceMatch && !init?.method) {
        const username = decodeURIComponent(workspaceMatch[1]);
        return registeredWorkspaces.has(username)
          ? jsonResponse({ username, created_at: now })
          : Promise.resolve({
              ok: false,
              status: 404,
              json: async () => ({ detail: "Workspace not found" }),
            } as Response);
      }
      if (path === "/api/v1/workspaces" && init?.method === "POST") {
        const username = JSON.parse(String(init.body)).username;
        registeredWorkspaces.add(username);
        return jsonResponse({ username, created_at: now });
      }
      if (path.endsWith(`/api/v1/agents/${agent.id}/memories`) && init?.method === "POST") {
        return jsonResponse({ ...memory, content: JSON.parse(String(init.body)).content });
      }
      if (path.endsWith(`/api/v1/agents/${agent.id}/memories`)) {
        return jsonResponse({ memories: [memory] });
      }
      if (path.endsWith(`/api/v1/agents/${agent.id}/memories/${memory.id}`)) {
        if (init?.method === "DELETE") return Promise.resolve({ ok: true, status: 204 } as Response);
        return jsonResponse({ ...memory, enabled: JSON.parse(String(init?.body)).enabled });
      }
      if (path === "/api/v1/llm/providers") {
        return jsonResponse({ providers: [
          { provider: "mock", display_name: "Mock", default_model: "mock-echo", allow_custom_model: false,
            models: [{ model: "mock-echo", display_name: "Mock Echo", config: { provider: "mock", model: "mock-echo" } }] },
          { provider: "openai", display_name: "OpenAI", default_model: "gpt-5.6-luna", allow_custom_model: true,
            models: [
              { model: "gpt-5.6-luna", display_name: "GPT-5.6 Luna", config: { provider: "openai", model: "gpt-5.6-luna" } },
              { model: "gpt-5.6-sol", display_name: "GPT-5.6 Sol", config: { provider: "openai", model: "gpt-5.6-sol" } },
            ] },
        ] });
      }
      if (path === "/api/v1/llm/config" && !init?.method) {
        return jsonResponse({ provider: "mock", model: "mock-echo", base_url: "mock://local",
          api_key_configured: false, api_key_source: "not_required" });
      }
      if (path === "/api/v1/llm/config" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        return jsonResponse({ provider: body.provider, model: body.model,
          base_url: body.provider === "mock" ? "mock://local" : "https://api.openai.com/v1",
          api_key_configured: body.provider !== "mock", api_key_source: body.provider === "mock" ? "not_required" : "request" });
      }
      if (path === "/api/v1/codex/status") {
        return jsonResponse({
          installed: true,
          authenticated: true,
          auth_mode: "chatgpt",
          plan_type: "plus",
          windows: [
            { name: "primary", used_percent: 53, window_minutes: 300, resets_at: 1789303661 },
            { name: "secondary", used_percent: 20, window_minutes: 10080, resets_at: 1789805406 },
          ],
          error: null,
        });
      }
      if (path === "/api/v1/usage/runs?limit=100") return jsonResponse({ runs: [run] });
      if (path === "/api/v1/skills") return jsonResponse({ skills: [skill] });
      if (path === "/api/v1/knowledge/sources" && init?.method === "POST") {
        return jsonResponse({ ...knowledgeSource, ...JSON.parse(String(init.body)) });
      }
      if (path === "/api/v1/runtime/policy") {
        return jsonResponse({
          demo_mode: demoMode,
          blocked_tool_risks: demoMode ? ["local_write", "external_write"] : [],
        });
      }
      if (path === "/api/v1/knowledge/sources") return jsonResponse({ sources: [knowledgeSource] });
      if (path === `/api/v1/knowledge/sources/${knowledgeSource.id}/sync` && init?.method === "POST") {
        return jsonResponse({ source_id: knowledgeSource.id, status: "ready", scanned: 1, created: 0, updated: 0, deleted: 0, unchanged: 1, chunks: 1 });
      }
      if (path === `/api/v1/knowledge/sources/${knowledgeSource.id}/embeddings/index` && init?.method === "POST") {
        return jsonResponse({ source_id: knowledgeSource.id, provider: "local", model: "test", indexed: 1, unchanged: 0 });
      }
      if (path === `/api/v1/agents/${agent.id}/skills` && init?.method === "PUT") {
        return jsonResponse({ ...agent, skill_ids: JSON.parse(String(init.body)).skill_ids });
      }
      if (path === `/api/v1/agents/${agent.id}/knowledge-sources` && init?.method === "PUT") {
        return jsonResponse({ ...agent, knowledge_source_ids: JSON.parse(String(init.body)).knowledge_source_ids });
      }
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
        return jsonResponse({ ...agent, id: "agent-created", ...JSON.parse(String(init.body)) });
      }
      if (path === `/api/v1/agents/${agent.id}` && init?.method === "PATCH") {
        return jsonResponse({ ...agent, ...JSON.parse(String(init.body)) });
      }
      if (path === "/api/v1/agents") return jsonResponse({ agents: [agent, reviewer] });
      if (path === "/api/v1/sessions" && init?.method === "POST") {
        return jsonResponse({ ...session, id: "session-2", title: "新会话" });
      }
      if (path === "/api/v1/sessions") return jsonResponse({ sessions: [session, reviewerSession] });
      if (path.includes("session-2/messages") || path.includes("session-review/messages")) {
        return jsonResponse({ messages: [] });
      }
      if (path.includes("/messages")) {
        return jsonResponse({
          messages: [{
            id: "message-1",
            client_id: "local-demo",
            session_id: session.id,
            agent_id: agent.id,
            run_id: "run-1",
            role: "assistant",
            content: "**历史回答 **\n\n1. 第一项",
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
    expect((await screen.findByText("历史回答")).tagName).toBe("STRONG");
    expect(screen.getByText("第一项").closest("li")).not.toBeNull();
    expect(screen.getByRole("combobox", { name: "聊天记录" })).toHaveValue(session.id);
    expect(screen.getByText("帮助我整理项目。")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/agents",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-Client-ID": "local-demo" }),
      }),
    );
  });

  it("opens the selected Agent's most recent session", async () => {
    renderApp();
    expect(await screen.findByRole("heading", { name: "项目计划" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Reviewer/ }));

    expect(await screen.findByRole("heading", { name: "代码审查" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "聊天记录" })).toHaveValue(reviewerSession.id);
    expect(screen.getByText("Reviewer · codex")).toBeInTheDocument();
  });

  it("retries active resource requests after a server error", async () => {
    const mockedFetch = vi.mocked(fetch);
    const fallback = mockedFetch.getMockImplementation()!;
    let failed = false;
    mockedFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      if (!failed && String(input) === "/api/v1/agents") {
        failed = true;
        return Promise.resolve({
          ok: false,
          status: 503,
          json: async () => ({ detail: "Agent 列表暂时不可用" }),
        } as Response);
      }
      return fallback(input, init);
    });

    renderApp();
    expect(await screen.findByText("Agent 列表暂时不可用")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试" }));

    await waitFor(() => {
      expect(screen.queryByText("Agent 列表暂时不可用")).not.toBeInTheDocument();
    });
    expect(await screen.findByRole("button", { name: /Personal/ })).toBeInTheDocument();
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
      socket.emit({ type: "assistant_delta", run_id: "run-2", sequence: null, payload: { text: "**这是流式回答**" } });
      socket.emit({ type: "run_finished", run_id: "run-2", sequence: 2, payload: { duration_ms: 120 } });
    });

    expect(screen.getByText("解释状态图")).toBeInTheDocument();
    expect(screen.getByText("这是流式回答").tagName).toBe("STRONG");
    expect(screen.getByText("这是流式回答").closest("article")).toHaveTextContent("🧠");
    expect(screen.getByText("这是流式回答").closest("article")?.querySelector(".stream-cursor")).toBeNull();
    expect(screen.getByText("这是流式回答").closest("article")?.querySelector("time"))
      .not.toHaveTextContent("正在输入");
    expect(screen.getAllByText("运行完成")).toHaveLength(2);
  });

  it("shows when the server is running in restricted demo mode", async () => {
    demoMode = true;
    renderApp();

    const badge = await screen.findByText("Demo · 写入已禁用");
    expect(badge).toHaveAttribute(
      "title", "禁用风险：local_write、external_write",
    );
  });

  it("shows a failed tool with its safe error type", async () => {
    renderApp();
    const composer = screen.getByLabelText("消息");
    await waitFor(() => expect(composer).toBeEnabled());
    fireEvent.change(composer, { target: { value: "打开网页" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    act(() => {
      const socket = FakeWebSocket.instances[0];
      socket.emit({ type: "run_started", run_id: "run-error", sequence: 1, payload: {} });
      socket.emit({
        type: "tool_finished", run_id: "run-error", sequence: 2,
        payload: { tool_name: "mcp_browser_navigate", status: "error", error_type: "MCPError" },
      });
      socket.emit({
        type: "run_failed", run_id: "run-error", sequence: 3,
        payload: { error_type: "MCPError" },
      });
    });

    expect(screen.getByText("工具失败")).toBeInTheDocument();
    expect(screen.getByText("mcp_browser_navigate · MCPError")).toBeInTheDocument();
  });

  it("reviews and approves a Markdown tool call", async () => {
    renderApp();
    const composer = screen.getByLabelText("消息");
    await waitFor(() => expect(composer).toBeEnabled());
    fireEvent.change(composer, { target: { value: "更新笔记" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    const socket = FakeWebSocket.instances[0];

    act(() => socket.emit({
      type: "approval_required",
      run_id: "run-write",
      sequence: 2,
      payload: {
        approval_id: "approval-1",
        tool_name: "write_markdown",
        path: "D:/projects/笔记/today.md",
        content_preview: "# Today",
      },
    }));

    expect(screen.getByText("D:/projects/笔记/today.md")).toBeInTheDocument();
    expect(screen.getByText("# Today")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "批准写入" }));
    expect(JSON.parse(socket.sent[1])).toEqual({
      type: "tool_approval",
      run_id: "run-write",
      approval_id: "approval-1",
      approved: true,
    });
  });
  it("shows a safe Gmail approval summary without the message body", async () => {
    renderApp();
    const composer = screen.getByLabelText("消息");
    await waitFor(() => expect(composer).toBeEnabled());
    fireEvent.change(composer, { target: { value: "发送邮件" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    const socket = FakeWebSocket.instances[0];

    act(() => socket.emit({
      type: "approval_required",
      run_id: "run-email",
      sequence: 2,
      payload: {
        approval_id: "approval-email",
        tool_name: "gmail_send_message",
        risk: "external_write",
        summary: {
          action: "send_message",
          recipients: "candidate@example.com",
          cc: "reviewer@example.com",
          subject: "Interview",
        },
      },
    }));

    expect(screen.getByText("candidate@example.com")).toBeInTheDocument();
    expect(screen.getByText("reviewer@example.com")).toBeInTheDocument();
    expect(screen.getByText("Interview")).toBeInTheDocument();
    expect(screen.queryByText("secret email body")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "批准执行" }));
    expect(JSON.parse(socket.sent[1])).toEqual({
      type: "tool_approval",
      run_id: "run-email",
      approval_id: "approval-email",
      approved: true,
    });
  });
  it("hands a message to an @mentioned Agent", async () => {
    renderApp();
    const composer = screen.getByLabelText("消息");
    await waitFor(() => expect(composer).toBeEnabled());

    fireEvent.change(composer, { target: { value: "请@Rev" } });
    fireEvent.click(await screen.findByRole("option", { name: /@Reviewer/ }));
    expect(composer).toHaveValue("请@Reviewer ");
    expect(screen.getByText("Personal → Reviewer")).toBeInTheDocument();
    fireEvent.change(composer, { target: { value: "让@Reviewer 请审查这段实现" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    const socket = FakeWebSocket.instances[0];
    expect(JSON.parse(socket.sent[0])).toEqual({
      type: "send_message",
      session_id: session.id,
      content: "让 请审查这段实现",
      target_agent_id: reviewer.id,
    });

    act(() => {
      socket.emit({
        type: "handoff_started", run_id: "run-handoff", sequence: 1,
        payload: { from_agent_id: agent.id, to_agent_id: reviewer.id, mode: "manual" },
      });
      socket.emit({
        type: "handoff_finished", run_id: "run-handoff", sequence: 2,
        payload: { from_agent_id: agent.id, to_agent_id: reviewer.id, mode: "manual" },
      });
      socket.emit({
        type: "assistant_delta", run_id: "run-handoff", sequence: null,
        payload: { text: "审查完成" },
      });
    });
    expect(screen.getAllByText("Personal → Reviewer · 手动转交")).toHaveLength(2);
    expect(screen.getByText("审查完成").closest("article")).toHaveTextContent("Reviewer");
    expect(screen.getByText("审查完成").closest("article")).toHaveTextContent("🔎");
  });

  it("switches the current Agent model from the composer", async () => {
    renderApp();
    const selector = await screen.findByRole("combobox", { name: "当前 Agent 模型" });
    await waitFor(() => expect(selector).toBeEnabled());
    fireEvent.change(selector, { target: { value: "gpt-5.6-sol" } });

    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      `/api/v1/agents/${agent.id}`,
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ model: "gpt-5.6-sol" }) }),
    ));
  });

  it("shows persisted run and usage details", async () => {
    renderApp();
    await screen.findByRole("heading", { name: "项目计划" });

    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(await screen.findByText("gpt-5.6-luna")).toBeInTheDocument();
    expect(screen.getByText("680 ms / 120 ms")).toBeInTheDocument();
    expect(screen.getByText("daily-planning · abcdef12")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Usage" }));
    expect(screen.getByText("Workspace 总计")).toBeInTheDocument();
    expect(screen.getAllByText("120")).toHaveLength(2);
    expect(screen.getAllByText("$0.001230")).toHaveLength(2);
  });


  it("shows Codex remaining limits for a Codex conversation", async () => {
    renderApp();
    const codexAgent = await screen.findByRole("button", { name: /Reviewer.*Codex CLI/ });
    fireEvent.click(codexAgent);
    expect(screen.getByRole("combobox", { name: "当前 Agent 模型" })).toHaveTextContent("Codex CLI");
    fireEvent.click(screen.getByRole("button", { name: "Usage" }));

    expect(await screen.findByText("Codex 剩余额度")).toBeInTheDocument();
    expect(screen.getByText("剩余 47%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "5 小时剩余额度" })).toHaveValue(47);
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/codex/status",
      expect.objectContaining({ headers: expect.objectContaining({ "X-Client-ID": "local-demo" }) }),
    );
  });
  it("manages Agent memory through the API", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Memory" }));
    expect(await screen.findByText(memory.content)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("禁用记忆"));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      `/api/v1/agents/${agent.id}/memories/${memory.id}`,
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ enabled: false }) }),
    ));

    fireEvent.change(screen.getByLabelText("新增长期记忆"), { target: { value: "记住项目目标" } });
    fireEvent.click(screen.getByRole("button", { name: "添加记忆" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      `/api/v1/agents/${agent.id}/memories`,
      expect.objectContaining({ method: "POST", body: JSON.stringify({ content: "记住项目目标" }) }),
    ));

    fireEvent.click(screen.getByRole("button", { name: "删除记忆" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      `/api/v1/agents/${agent.id}/memories/${memory.id}`,
      expect.objectContaining({ method: "DELETE" }),
    ));
  });
  it("creates an Agent with the selected default model", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "创建 Agent" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "保存" })).toBeEnabled());
    fireEvent.change(screen.getByPlaceholderText("例如：Personal"), { target: { value: "Reviewer" } });
    fireEvent.change(screen.getByPlaceholderText("说明 Agent 的职责和行为边界"), { target: { value: "Review code." } });
    fireEvent.change(screen.getByRole("combobox", { name: "Agent 头像 Emoji" }), { target: { value: "💻" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/v1/agents",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "Reviewer", avatar_emoji: "💻", system_prompt: "Review code.", provider: "mock", model: "mock-echo", runtime: "native" }),
      }),
    ));
  });
  it("creates a Codex CLI Agent for a server project", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "创建 Agent" }));
    await screen.findByRole("option", { name: "Codex CLI" });
    fireEvent.change(screen.getByRole("combobox", { name: "Agent 运行时" }), {
      target: { value: "codex" },
    });
    fireEvent.change(screen.getByPlaceholderText("例如：Personal"), {
      target: { value: "Coder" },
    });
    fireEvent.change(screen.getByLabelText("服务端项目目录"), {
      target: { value: "server" },
    });
    expect(screen.getByText(/Codex 在服务器上运行/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/v1/agents",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Coder", avatar_emoji: "🤖", system_prompt: "Codex CLI proxy",
          runtime: "codex", provider: null, model: null, workspace_path: "server",
        }),
      }),
    ));
  });
  it("edits an existing Agent provider and model", async () => {
    renderApp();
    await screen.findByRole("heading", { name: "项目计划" });
    fireEvent.click(screen.getByRole("button", { name: "编辑 Agent" }));
    await screen.findByRole("option", { name: "OpenAI" });
    fireEvent.change(screen.getByRole("combobox", { name: "Agent 厂商" }), {
      target: { value: "openai" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Agent 头像 Emoji" }), {
      target: { value: "🐙" },
    });
    fireEvent.change(screen.getByLabelText("API Key（首次使用该厂商时填写）"), {
      target: { value: "agent-key" },
    });
    await waitFor(() => expect(screen.getByRole("button", { name: "保存" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      `/api/v1/agents/${agent.id}`,
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          name: "Personal", avatar_emoji: "🐙", system_prompt: "帮助我整理项目。",
          provider: "openai", model: "gpt-5.6-luna",
        }),
      }),
    ));
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/llm/config",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ provider: "openai", model: "gpt-5.6-luna", api_key: "agent-key" }),
      }),
    );
  });
  it("switches the REST and WebSocket workspace to a custom user ID", async () => {
    renderApp();
    await screen.findByRole("heading", { name: "项目计划" });
    fireEvent.click(screen.getByRole("button", { name: "设置" }));

    const input = await screen.findByLabelText("用户 ID");
    fireEvent.change(input, { target: { value: "New_User" } });
    fireEvent.click(screen.getByRole("button", { name: "打开或创建用户" }));

    await waitFor(() => {
      expect(window.localStorage.getItem("personal-agent-workspace-id")).toBe("new_user");
    });
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/workspaces",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ username: "new_user" }),
      }),
    );
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/v1/agents",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-Client-ID": "new_user" }),
      }),
    ));
    expect(FakeWebSocket.instances.at(-1)?.url).toContain("client_id=new_user");
    expect(screen.queryByRole("heading", { name: "工作区设置" })).not.toBeInTheDocument();
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

  it("enables a discovered Skill for a Native Agent", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "设置" }));

    const toggle = await screen.findByRole("checkbox", { name: "启用 每日工作规划" });
    fireEvent.click(toggle);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      `/api/v1/agents/${agent.id}/skills`,
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ skill_ids: ["daily-planning"] }),
      }),
    ));
  });

  it("manages the RAG directory lifecycle and Agent binding", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "设置" }));
    expect(await screen.findByRole("button", { name: "同步 Project Notes" })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("例如：Obsidian Vault"), { target: { value: "Interview Notes" } });
    fireEvent.change(screen.getByPlaceholderText("D:\\Notes\\Vault"), { target: { value: "D:\\Notes\\Interview" } });
    fireEvent.click(screen.getByRole("button", { name: "添加目录" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/v1/knowledge/sources",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ name: "Interview Notes", root_path: "D:\\Notes\\Interview", source_type: "obsidian" }) }),
    ));

    fireEvent.click(screen.getByRole("button", { name: "同步 Project Notes" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      `/api/v1/knowledge/sources/${knowledgeSource.id}/sync`, expect.objectContaining({ method: "POST" }),
    ));
    await waitFor(() => expect(screen.getByRole("button", { name: "向量化 Project Notes" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "向量化 Project Notes" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      `/api/v1/knowledge/sources/${knowledgeSource.id}/embeddings/index`, expect.objectContaining({ method: "POST" }),
    ));

    await waitFor(() => expect(screen.getByRole("checkbox", { name: "绑定 Project Notes" })).toBeEnabled());
    fireEvent.click(screen.getByRole("checkbox", { name: "绑定 Project Notes" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      `/api/v1/agents/${agent.id}/knowledge-sources`,
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ knowledge_source_ids: [knowledgeSource.id] }) }),
    ));
  });

  it("shows the server Codex login and rate limits", async () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "设置" }));

    expect(await screen.findByText("已通过 chatgpt 登录 · plus")).toBeInTheDocument();
    expect(screen.getByText("5 小时额度")).toBeInTheDocument();
    expect(screen.getByText("剩余 47%")).toBeInTheDocument();
    expect(screen.getByText("周额度")).toBeInTheDocument();
  });
});
