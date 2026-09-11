import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BrainCircuit,
  CirclePlus,
  FileText,
  LoaderCircle,
  MessageSquareText,
  Plus,
  RotateCcw,
  Send,
  Settings,
  Square,
  Sparkles,
  X,
} from "lucide-react";
import { FormEvent, KeyboardEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { WorkspaceInspector } from "../features/inspector/WorkspaceInspector";
import { LiveRun, useRunStream } from "../features/runs/useRunStream";
import { WorkspaceSettings } from "../features/settings/WorkspaceSettings";
import {
  Agent,
  workspaceApi,
  WorkspaceSession,
} from "../shared/api/workspace";

type CreateDialog = "agent" | "session" | "settings" | null;

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

const eventLabels: Record<string, string> = {
  run_started: "运行开始",
  agent_started: "Agent 启动",
  agent_status: "Agent 状态",
  retrieval_started: "检索知识库",
  retrieval_result: "检索完成",
  context_prepared: "上下文已组装",
  tool_started: "工具调用",
  tool_finished: "工具完成",
  handoff_requested: "请求转交",
  handoff_started: "开始转交",
  handoff_finished: "转交完成",
  usage_updated: "用量更新",
  run_finished: "运行完成",
  run_failed: "运行失败",
  run_cancelled: "运行取消",
};

function eventDetail(type: string, payload: Record<string, unknown>, agents: Agent[]) {
  if (type.startsWith("handoff_")) {
    const agentName = (id: unknown) =>
      agents.find((agent) => agent.id === String(id || ""))?.name;
    const from = agentName(payload.from_agent_id);
    const to = agentName(payload.to_agent_id);
    const route = from && to ? `${from} → ${to}` : to || "Agent 已切换";
    const mode = payload.mode === "automatic" ? "自动转交" : "手动转交";
    return payload.task_summary
      ? `${route} · ${mode} · ${String(payload.task_summary)}`
      : `${route} · ${mode}`;
  }
  if (type === "usage_updated") {
    return `${payload.provider || "provider"} · ${payload.model || "model"} · ${payload.input_tokens ?? "?"}/${payload.output_tokens ?? "?"} tokens`;
  }
  if (type === "run_finished" || type === "run_failed" || type === "run_cancelled") {
    return payload.duration_ms == null ? "终态已持久化" : `${payload.duration_ms} ms`;
  }
  if (type === "retrieval_result") return "候选与命中片段已记录";
  return String(payload.message || payload.status || "事件已记录");
}

function RunCard({ run, agents }: { run: LiveRun; agents: Agent[] }) {
  const statusLabel = {
    idle: "等待",
    running: "运行中",
    completed: "运行完成",
    failed: "运行失败",
    cancelled: "已取消",
  }[run.status];
  return (
    <article className="run-card">
      <div className="run-card-title">
        <Sparkles size={16} /><b>LangGraph Run</b><span className={run.status}>{statusLabel}</span>
      </div>
      {run.events.map((event, index) => (
        <div className="run-event" key={`${event.type}-${event.sequence ?? index}`}>
          <span className="event-dot" />
          <b>{eventLabels[event.type] || event.type}</b>
          <span>{eventDetail(event.type, event.payload, agents)}</span>
          <time>{event.sequence == null ? "live" : `#${event.sequence}`}</time>
        </div>
      ))}
    </article>
  );
}

export function App() {
  const queryClient = useQueryClient();
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [dialog, setDialog] = useState<CreateDialog>(null);
  const [draft, setDraft] = useState("");
  const [targetAgentId, setTargetAgentId] = useState("");
  const sessionsInitialized = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
  const runsQuery = useQuery({
    queryKey: ["runs"],
    queryFn: workspaceApi.listRuns,
  });
  const usageQuery = useQuery({
    queryKey: ["usage"],
    queryFn: workspaceApi.getUsageSummary,
  });
  const agents = agentsQuery.data ?? [];
  const sessions = sessionsQuery.data ?? [];
  const stream = useRunStream((runId, sessionId) => {
    void queryClient.invalidateQueries({ queryKey: ["messages", sessionId] });
    void queryClient.invalidateQueries({ queryKey: ["usage"] });
    if (runId) void queryClient.invalidateQueries({ queryKey: ["runs"] });
  });

  useEffect(() => {
    if (!selectedAgentId && agents[0]) setSelectedAgentId(agents[0].id);
  }, [agents, selectedAgentId]);

  useEffect(() => {
    if (!sessionsInitialized.current && sessionsQuery.isSuccess) {
      sessionsInitialized.current = true;
      if (sessions[0]) {
        setSelectedSessionId(sessions[0].id);
        setSelectedAgentId(sessions[0].agent_id);
      }
    }
  }, [sessions, sessionsQuery.isSuccess]);

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedAgentId),
    [agents, selectedAgentId],
  );
  const selectedSession = sessions.find(
    (session) => session.id === selectedSessionId,
  );
  const agentById = new Map(agents.map((agent) => [agent.id, agent]));
  const sessionAgent = selectedSession
    ? agentById.get(selectedSession.agent_id)
    : selectedAgent;
  const liveHere = stream.run.sessionId === selectedSessionId;
  const visibleMessages = messagesQuery.data?.filter(
    (message) => !liveHere || !stream.run.runId || message.run_id !== stream.run.runId,
  );
  const liveAgentId = [...stream.run.events].reverse().find(
    (event) => event.type === "handoff_finished",
  )?.payload.to_agent_id;
  const liveAgent = agentById.get(String(liveAgentId || sessionAgent?.id || ""));

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ block: "end" });
  }, [selectedSessionId, visibleMessages?.length, stream.run.assistantText, stream.run.events.length]);

  function selectSession(session: WorkspaceSession) {
    setSelectedSessionId(session.id);
    setSelectedAgentId(session.agent_id);
    setTargetAgentId("");
  }

  function selectAgent(agent: Agent) {
    const recentSession = sessions.find((session) => session.agent_id === agent.id);
    setSelectedAgentId(agent.id);
    setTargetAgentId("");
    if (recentSession) selectSession(recentSession);
    else setSelectedSessionId("");
  }

  function retryResources() {
    void queryClient.refetchQueries({ type: "active" });
  }

  function submitMessage(event?: FormEvent<HTMLFormElement> | KeyboardEvent<HTMLTextAreaElement>) {
    event?.preventDefault();
    const content = draft.trim();
    if (!selectedSession || !content || stream.run.status === "running") return;
    stream.send(selectedSession.id, content, targetAgentId || undefined);
    setDraft("");
    setTargetAgentId("");
  }

  const queryError = agentsQuery.error || sessionsQuery.error || messagesQuery.error
    || runsQuery.error || usageQuery.error;
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
              onClick={() => selectAgent(agent)}
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
        <button className="settings" onClick={() => setDialog("settings")}><Settings size={15} />设置</button>
      </aside>

      <section className="conversation">
        <header className="conversation-header">
          <div>
            <div className="conversation-title-row">
              <h1>{selectedSession?.title || "个人 Agent 工作台"}</h1>
              <select
                aria-label="聊天记录"
                disabled={!sessions.length}
                value={selectedSessionId}
                onChange={(event) => {
                  const next = sessions.find((item) => item.id === event.target.value);
                  if (next) selectSession(next);
                }}
              >
                {!selectedSession && <option value="">选择聊天记录</option>}
                {sessions.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
              </select>
            </div>
            <p>
              <span className="status-dot" />
              {sessionAgent
                ? `${sessionAgent.name} · ${sessionAgent.runtime}`
                : selectedAgent
                  ? `${selectedAgent.name} · 尚未创建会话`
                  : "选择或创建一个 Agent"}
            </p>
          </div>
          <span className={`connection-badge ${queryError || stream.connection === "closed" ? "error" : ""}`}>
            {queryError ? "资源请求失败"
              : resourcesLoading ? "资源加载中"
              : stream.connection === "open" ? "实时已连接"
              : stream.connection === "connecting" ? "实时连接中" : "实时连接断开"}
          </span>
        </header>

        <div className="messages" aria-live="polite">
          {queryError && (
            <div className="error-banner error-with-action">
              <span>{queryError.message}</span>
              <button type="button" onClick={retryResources}>
                <RotateCcw size={13} />重试
              </button>
            </div>
          )}
          {messagesQuery.isLoading && <LoaderCircle className="spinner center" />}
          {visibleMessages?.map((message) => {
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
          {liveHere && stream.run.userText && (
            <article className="message user-message live-message">
              <p>{stream.run.userText}</p><time>刚刚</time>
            </article>
          )}
          {liveHere && stream.run.events.length > 0 && <RunCard run={stream.run} agents={agents} />}
          {liveHere && stream.run.assistantText && (
            <article className="message assistant-message live-message">
              <div className="message-author"><Sparkles size={14} />{liveAgent?.name || "Agent"}</div>
              <p>{stream.run.assistantText}<span className="stream-cursor" /></p>
            </article>
          )}
          {liveHere && stream.run.error && <div className="error-banner">{stream.run.error}</div>}
          {selectedSession && !messagesQuery.isLoading && !messagesQuery.data?.length && !liveHere && (
            <EmptyState>
              <MessageSquareText size={28} />
              <b>开始这段对话</b>
              <span>消息、Agent 转交和运行状态会实时显示在这里。</span>
            </EmptyState>
          )}
          {!selectedSession && !sessionsQuery.isLoading && (
            <EmptyState>
              <BrainCircuit size={30} />
              <b>{agents.length ? "创建一个新对话" : "先创建你的第一个 Agent"}</b>
              <span>每个会话都会保留消息、运行事件和用量记录。</span>
            </EmptyState>
          )}
          <div className="messages-end" ref={messagesEndRef} aria-hidden="true" />
        </div>

        <form className="composer" onSubmit={submitMessage}>
          <textarea
            aria-label="消息"
            disabled={!selectedSession || stream.connection !== "open" || stream.run.status === "running"}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) submitMessage(event);
            }}
            placeholder={selectedSession ? `向 ${sessionAgent?.name || "Agent"} 发送消息…` : "先选择一个会话"}
          />
          <div className="composer-actions">
            <div className="handoff-control">
              <select
                aria-label="转交给 Agent"
                disabled={!selectedSession || stream.run.status === "running"}
                value={targetAgentId}
                onChange={(event) => setTargetAgentId(event.target.value)}
              >
                <option value="">由 {sessionAgent?.name || "会话 Agent"} 执行</option>
                {agents.filter((agent) => agent.id !== selectedSession?.agent_id).map((agent) => (
                  <option key={agent.id} value={agent.id}>转交给 {agent.name}</option>
                ))}
              </select>
              {targetAgentId && (
                <span className="handoff-preview">
                  {sessionAgent?.name} → {agentById.get(targetAgentId)?.name}
                </span>
              )}
            </div>
            {stream.run.status === "running" ? (
              <button type="button" aria-label="停止运行" disabled={!stream.run.runId} onClick={stream.cancel}>
                <Square size={15} />
              </button>
            ) : (
              <button type="submit" aria-label="发送" disabled={!draft.trim() || stream.connection !== "open"}>
                <Send size={17} />
              </button>
            )}
          </div>
        </form>
      </section>

      <WorkspaceInspector
        agent={selectedAgent}
        session={selectedSession}
        sessions={sessions}
        messageCount={messagesQuery.data?.length ?? 0}
        runs={runsQuery.data ?? []}
        summary={usageQuery.data}
        loading={runsQuery.isLoading}
      />

      {dialog === "settings" && <WorkspaceSettings onClose={() => setDialog(null)} />}
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
  const providersQuery = useQuery({ queryKey: ["llm-providers"], queryFn: workspaceApi.listLLMProviders });
  const configQuery = useQuery({ queryKey: ["llm-config"], queryFn: workspaceApi.getLLMConfig });
  const [model, setModel] = useState("");
  const provider = providersQuery.data?.find((item) => item.provider === configQuery.data?.provider);
  useEffect(() => {
    if (configQuery.data) setModel(configQuery.data.model);
  }, [configQuery.data]);
  const mutation = useMutation({ mutationFn: workspaceApi.createAgent, onSuccess: onCreated });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      name: String(data.get("name")),
      system_prompt: String(data.get("system_prompt")),
      runtime: "native",
      model,
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
        <label>
          默认模型
          <select aria-label="Agent 默认模型" required value={model} onChange={(event) => setModel(event.target.value)}>
            {provider?.models.map((item) => (
              <option key={item.model} value={item.model}>{item.display_name}</option>
            ))}
          </select>
          <small className="field-hint">Provider：{configQuery.data?.provider || "读取中"}，可在设置中切换。</small>
        </label>
        {mutation.error && <p className="form-error">{mutation.error.message}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onClose}>取消</button>
          <button className="primary" disabled={!model || mutation.isPending}>{mutation.isPending ? "创建中…" : "创建"}</button>
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
