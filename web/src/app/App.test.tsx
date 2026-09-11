import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
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

    expect(await screen.findByText("项目计划")).toBeInTheDocument();
    expect(await screen.findByText("历史回答")).toBeInTheDocument();
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
});
