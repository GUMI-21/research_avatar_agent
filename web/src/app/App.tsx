import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  BrainCircuit,
  CirclePlus,
  Database,
  FileText,
  LoaderCircle,
  MessageSquareText,
  Plus,
  Send,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";

import {
  Agent,
  workspaceApi,
  WorkspaceSession,
} from "../shared/api/workspace";

type CreateDialog = "agent" | "session" | null;

function agentInitial(name: string) {
  return name.trim().charAt(0).toUpperCase() || "A";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

export function App() {
  const queryClient = useQueryClient();
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [dialog, setDialog] = useState<CreateDialog>(null);

  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: workspaceApi.listAgents,
  });
  const sessionsQuery = useQuery({
    queryKey: ["sessions"],
    queryFn: workspaceApi.listSessions,
  });
  const messagesQuery = useQuery({
    queryKey: ["messages", selectedSessionId],
    queryFn: () => workspaceApi.listMessages(selectedSessionId),
    enabled: Boolean(selectedSessionId),
  });
  const agents = agentsQuery.data ?? [];
  const sessions = sessionsQuery.data ?? [];

  useEffect(() => {
    if (!selectedAgentId && agents[0]) setSelectedAgentId(agents[0].id);
  }, [agents, selectedAgentId]);

  useEffect(() => {
    if (!selectedSessionId && sessions[0]) {
      setSelectedSessionId(sessions[0].id);
      setSelectedAgentId(sessions[0].agent_id);
    }
  }, [sessions, selectedSessionId]);

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedAgentId),
    [agents, selectedAgentId],
  );
  const selectedSession = sessions.find(
    (session) => session.id === selectedSessionId,
  );
  const agentById = new Map(agents.map((agent) => [agent.id, agent]));

  function selectSession(session: WorkspaceSession) {
    setSelectedSessionId(session.id);
    setSelectedAgentId(session.agent_id);
  }

  const queryError =
    agentsQuery.error || sessionsQuery.error || messagesQuery.error;
  const resourcesLoading = agentsQuery.isLoading || sessionsQuery.isLoading;

  return (
    <main className="workspace-shell">
      <aside className="sidebar">
        <div className="brand">
          <BrainCircuit size={20} />
          <span>Agent Workspace</span>
        </div>
        <button
          className="new-session"
          disabled={!agents.length}
          onClick={() => setDialog("session")}
        >
          <Plus size={16} />新建对话
        </button>

        <div className="section-heading">
          <p className="section-label">AGENTS</p>
          <button aria-label="创建 Agent" onClick={() => setDialog("agent")}>
            <CirclePlus size={15} />
          </button>
        </div>
        <div className="agent-list">
          {agentsQuery.isLoading && <LoaderCircle className="spinner" />}
          {agents.map((agent) => (
            <button
              className={`agent ${agent.id === selectedAgentId ? "active" : ""}`}
              key={agent.id}
              onClick={() => setSelectedAgentId(agent.id)}
            >
              <span className="avatar">{agentInitial(agent.name)}</span>
              <span>
                <b>{agent.name}</b>
                <small>{agent.runtime} · {agent.model || "默认模型"}</small>
              </span>
            </button>
          ))}
          {!agentsQuery.isLoading && !agents.length && (
            <button className="create-first" onClick={() => setDialog("agent")}>
              创建第一个 Agent
            </button>
          )}
        </div>

        <p className="section-label">RECENT SESSIONS</p>
        <nav className="sessions">
          {sessions.map((session) => (
            <button
              className={session.id === selectedSessionId ? "active" : ""}
              key={session.id}
              onClick={() => selectSession(session)}
            >
              <FileText size={14} />
              <span>{session.title}</span>
            </button>
          ))}
          {!sessionsQuery.isLoading && !sessions.length && (
            <small className="muted-copy">还没有对话</small>
          )}
        </nav>
        <button className="settings"><Settings size={15} />设置</button>
      </aside>

      <section className="conversation">
        <header className="conversation-header">
          <div>
            <h1>{selectedSession?.title || "个人 Agent 工作台"}</h1>
            <p>
              <span className="status-dot" />
              {selectedAgent
                ? `${selectedAgent.name} · ${selectedAgent.runtime}`
                : "选择或创建一个 Agent"}
            </p>
          </div>
          <span className={`connection-badge ${queryError ? "error" : ""}`}>
            {queryError ? "REST 请求失败" : resourcesLoading ? "REST 连接中" : "REST 已连接"}
          </span>
        </header>

        <div className="messages">
          {queryError && <div className="error-banner">{queryError.message}</div>}
          {messagesQuery.isLoading && <LoaderCircle className="spinner center" />}
          {messagesQuery.data?.map((message) => {
            const owner = agentById.get(message.agent_id);
            return (
              <article
                className={`message ${message.role === "user" ? "user-message" : "assistant-message"}`}
                key={message.id}
              >
                {message.role !== "user" && (
                  <div className="message-author">
                    <Sparkles size={14} />{owner?.name || "Agent"}
                  </div>
                )}
                <p>{message.content}</p>
                <time>{formatDate(message.created_at)}</time>
              </article>
            );
          })}
          {selectedSession && !messagesQuery.isLoading && !messagesQuery.data?.length && (
            <EmptyState>
              <MessageSquareText size={28} />
              <b>开始这段对话</b>
              <span>下一批将接入 WebSocket 流式运行。</span>
            </EmptyState>
          )}
          {!selectedSession && !sessionsQuery.isLoading && (
            <EmptyState>
              <BrainCircuit size={30} />
              <b>{agents.length ? "创建一个新对话" : "先创建你的第一个 Agent"}</b>
              <span>每个会话都会保留消息、运行事件和用量记录。</span>
            </EmptyState>
          )}
        </div>

        <form className="composer">
          <textarea
            aria-label="消息"
            disabled
            placeholder="WebSocket 流式消息将在下一批接入…"
          />
          <div>
            <span>当前批次已接入历史消息</span>
            <button type="button" aria-label="发送" disabled><Send size={17} /></button>
          </div>
        </form>
      </section>

      <aside className="inspector">
        <div className="inspector-tabs">
          <button className="active">Agent</button><button>Run</button><button>Usage</button>
        </div>
        {selectedAgent ? (
          <>
            <section>
              <h2><Bot size={15} />当前 Agent</h2>
              <div className="profile-card">
                <span className="avatar large">{agentInitial(selectedAgent.name)}</span>
                <div><b>{selectedAgent.name}</b><small>{selectedAgent.runtime}</small></div>
              </div>
            </section>
            <section>
              <h2><Sparkles size={15} />System Prompt</h2>
              <p className="reason">{selectedAgent.system_prompt}</p>
            </section>
            <section>
              <h2><Database size={15} />工作区数据</h2>
              <dl className="metrics">
                <div><dt>会话</dt><dd>{sessions.filter((item) => item.agent_id === selectedAgent.id).length}</dd></div>
                <div><dt>知识库</dt><dd>{selectedAgent.knowledge_source_ids.length}</dd></div>
                <div><dt>当前消息</dt><dd>{messagesQuery.data?.length ?? 0}</dd></div>
              </dl>
            </section>
          </>
        ) : (
          <EmptyState><Bot size={28} /><span>选择 Agent 查看配置</span></EmptyState>
        )}
      </aside>

      {dialog === "agent" && (
        <AgentDialog
          onClose={() => setDialog(null)}
          onCreated={(agent) => {
            queryClient.setQueryData<Agent[]>(["agents"], (old = []) => [agent, ...old]);
            setSelectedAgentId(agent.id);
            setDialog(null);
          }}
        />
      )}
      {dialog === "session" && selectedAgent && (
        <SessionDialog
          agent={selectedAgent}
          onClose={() => setDialog(null)}
          onCreated={(session) => {
            queryClient.setQueryData<WorkspaceSession[]>(["sessions"], (old = []) => [session, ...old]);
            selectSession(session);
            setDialog(null);
          }}
        />
      )}
    </main>
  );
}

function AgentDialog({ onClose, onCreated }: {
  onClose: () => void;
  onCreated: (agent: Agent) => void;
}) {
  const mutation = useMutation({ mutationFn: workspaceApi.createAgent, onSuccess: onCreated });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      name: String(data.get("name")),
      system_prompt: String(data.get("system_prompt")),
    });
  }
  return (
    <div className="modal-backdrop">
      <form className="modal" onSubmit={submit}>
        <div className="modal-title">
          <div><small>NEW AGENT</small><h2>创建 Agent</h2></div>
          <button type="button" aria-label="关闭" onClick={onClose}><X size={18} /></button>
        </div>
        <label>名称<input name="name" required maxLength={80} placeholder="例如：Personal" /></label>
        <label>系统提示词<textarea name="system_prompt" required maxLength={50000} placeholder="说明 Agent 的职责和行为边界" /></label>
        {mutation.error && <p className="form-error">{mutation.error.message}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onClose}>取消</button>
          <button className="primary" disabled={mutation.isPending}>{mutation.isPending ? "创建中…" : "创建"}</button>
        </div>
      </form>
    </div>
  );
}

function SessionDialog({ agent, onClose, onCreated }: {
  agent: Agent;
  onClose: () => void;
  onCreated: (session: WorkspaceSession) => void;
}) {
  const mutation = useMutation({ mutationFn: workspaceApi.createSession, onSuccess: onCreated });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutation.mutate({ agent_id: agent.id, title: String(data.get("title")) });
  }
  return (
    <div className="modal-backdrop">
      <form className="modal" onSubmit={submit}>
        <div className="modal-title">
          <div><small>NEW SESSION</small><h2>与 {agent.name} 对话</h2></div>
          <button type="button" aria-label="关闭" onClick={onClose}><X size={18} /></button>
        </div>
        <label>对话标题<input name="title" required maxLength={160} autoFocus placeholder="这次要完成什么？" /></label>
        {mutation.error && <p className="form-error">{mutation.error.message}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onClose}>取消</button>
          <button className="primary" disabled={mutation.isPending}>{mutation.isPending ? "创建中…" : "开始对话"}</button>
        </div>
      </form>
    </div>
  );
}
