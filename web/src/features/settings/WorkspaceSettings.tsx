import { useMutation, useQuery } from "@tanstack/react-query";
import { Blocks, Bot, ChevronDown, KeyRound, ServerCog, UserRound, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { Agent, LLMConfigResponse, workspaceApi } from "../../shared/api/workspace";
import { KnowledgeSettings } from "./KnowledgeSettings";

type Props = {
  clientId: string;
  agents: Agent[];
  onClose: () => void;
  onAgentUpdated: (agent: Agent) => void;
  onWorkspaceChange: (clientId: string) => Promise<void>;
};

function limitLabel(minutes: number | null) {
  if (minutes === 300) return "5 小时额度";
  if (minutes === 10080) return "周额度";
  return minutes ? `${minutes} 分钟额度` : "额度窗口";
}

function remainingPercent(usedPercent: number) {
  return Math.max(0, Math.min(100, 100 - usedPercent));
}

export function WorkspaceSettings({ clientId, agents, onClose, onAgentUpdated, onWorkspaceChange }: Props) {
  const providersQuery = useQuery({
    queryKey: ["llm-providers"],
    queryFn: workspaceApi.listLLMProviders,
  });
  const configQuery = useQuery({
    queryKey: ["llm-config", clientId],
    queryFn: workspaceApi.getLLMConfig,
  });
  const codexQuery = useQuery({
    queryKey: ["codex-status"],
    queryFn: workspaceApi.getCodexStatus,
    refetchInterval: 60_000,
  });
  const mcpQuery = useQuery({
    queryKey: ["mcp-status"],
    queryFn: workspaceApi.getMCPStatus,
    refetchInterval: 60_000,
  });
  const skillsQuery = useQuery({ queryKey: ["skills"], queryFn: workspaceApi.listSkills });
  const [provider, setProvider] = useState("mock");
  const [model, setModel] = useState("mock-echo");
  const [username, setUsername] = useState(clientId);
  const [configured, setConfigured] = useState<LLMConfigResponse>();
  const nativeAgents = agents.filter((agent) => agent.runtime === "native");
  const [skillAgentId, setSkillAgentId] = useState(nativeAgents[0]?.id || "");
  const skillAgent = nativeAgents.find((agent) => agent.id === skillAgentId);
  const selected = providersQuery.data?.find((item) => item.provider === provider);
  const configMutation = useMutation({
    mutationFn: workspaceApi.configureLLM,
    onSuccess: setConfigured,
  });
  const workspaceMutation = useMutation({
    mutationFn: workspaceApi.ensureWorkspace,
    onSuccess: async (workspace) => {
      if (workspace.username !== clientId) await onWorkspaceChange(workspace.username);
    },
  });
  const skillsMutation = useMutation({
    mutationFn: ({ agentId, skillIds }: { agentId: string; skillIds: string[] }) =>
      workspaceApi.updateAgentSkills(agentId, skillIds),
    onSuccess: onAgentUpdated,
  });

  useEffect(() => {
    if (!configQuery.data) return;
    setProvider(configQuery.data.provider);
    setModel(configQuery.data.model);
    setConfigured(configQuery.data);
  }, [configQuery.data]);

  useEffect(() => {
    if (!skillAgentId && nativeAgents[0]) setSkillAgentId(nativeAgents[0].id);
  }, [skillAgentId, nativeAgents]);

  function selectProvider(value: string) {
    const option = providersQuery.data?.find((item) => item.provider === value);
    setProvider(value);
    setModel(option?.default_model || "");
    setConfigured(undefined);
  }

  function submitWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    workspaceMutation.mutate(username);
  }

  function submitConfig(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const apiKey = String(data.get("api_key") || "").trim();
    configMutation.mutate({
      provider,
      model,
      ...(apiKey ? { api_key: apiKey } : {}),
    });
  }

  return (
    <div className="modal-backdrop">
      <div className="modal settings-modal">
        <div className="modal-title">
          <div><small>WORKSPACE SETTINGS</small><h2>工作区设置</h2></div>
          <button type="button" aria-label="关闭" onClick={onClose}><X size={18} /></button>
        </div>

        <details className="settings-section" open>
          <summary><span><Blocks size={14} />RAG 知识库</span><small>本机目录</small><ChevronDown size={14} /></summary>
          <KnowledgeSettings agents={agents} onAgentUpdated={onAgentUpdated} />
        </details>

        <details className="settings-section" open>
          <summary>
            <span><Blocks size={14} />Skills</span>
            <small>{skillsQuery.data?.length ?? 0} 个已发现</small>
            <ChevronDown size={14} />
          </summary>
          <div className="skill-settings">
            <p className="settings-note">Skill 只向 Native Agent 注入工作流指令，不会扩大工具权限或绕过审批。</p>
            <label>Agent
              <select aria-label="Skill Agent" value={skillAgentId} onChange={(event) => setSkillAgentId(event.target.value)}>
                {nativeAgents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
              </select>
            </label>
            {skillsQuery.isLoading && <p className="inspector-muted">正在发现 Skills…</p>}
            {skillsQuery.error && <p className="form-error">{skillsQuery.error.message}</p>}
            {skillsQuery.data?.map((skill) => {
              const enabled = skillAgent?.skill_ids.includes(skill.id) ?? false;
              return (
                <label className="skill-option" key={skill.id}>
                  <input
                    aria-label={`启用 ${skill.name}`}
                    type="checkbox"
                    checked={enabled}
                    disabled={!skillAgent || skillsMutation.isPending}
                    onChange={() => skillAgent && skillsMutation.mutate({
                      agentId: skillAgent.id,
                      skillIds: enabled
                        ? skillAgent.skill_ids.filter((id) => id !== skill.id)
                        : [...skillAgent.skill_ids, skill.id],
                    })}
                  />
                  <span><b>{skill.name}</b><small>{skill.description}</small></span>
                </label>
              );
            })}
            {skillsMutation.error && <p className="form-error">{skillsMutation.error.message}</p>}
          </div>
        </details>

        <details className="settings-section" open>
          <summary>
            <span><ServerCog size={14} />MCP Servers</span>
            <small>{mcpQuery.data?.filter((item) => item.status === "connected").length ?? 0}/{mcpQuery.data?.length ?? 0} 已连接</small>
            <ChevronDown size={14} />
          </summary>
          <div className="mcp-status-list">
            <p className="inspector-muted">显示启动时的工具发现结果和运行期传输状态；调用错误记录在 Run 审计中。断连后需重启 Server 恢复连接。</p>
            {mcpQuery.isLoading && <p className="inspector-muted">正在读取 MCP 状态…</p>}
            {mcpQuery.error && <p className="form-error">无法读取 MCP 状态：{mcpQuery.error.message}</p>}
            {mcpQuery.data?.map((server) => (
              <div key={`${server.transport}:${server.name}`}>
                <b>{server.name} · {server.transport}</b>
                <span className={server.status}>
                  {server.status === "connected"
                    ? `${server.tool_count} tools`
                    : server.status === "unavailable"
                      ? server.error_type || "不可用"
                      : "待连接"}
                </span>
              </div>
            ))}
            {mcpQuery.data?.length === 0 && <p className="inspector-muted">未配置 MCP Server。</p>}
          </div>
        </details>

        <details className="settings-section" open>
          <summary><span><UserRound size={14} />用户 ID</span><small>{clientId}</small><ChevronDown size={14} /></summary>
          <form onSubmit={submitWorkspace}>
            <p className="settings-note">用户 ID 是本机工作区的唯一键，用于隔离 Agent、对话、Key 和用量。</p>
            <label>
              用户 ID
              <input
                aria-label="用户 ID"
                required
                minLength={1}
                maxLength={64}
                pattern="[A-Za-z0-9][A-Za-z0-9._-]*"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </label>
            {workspaceMutation.error && <p className="form-error">{workspaceMutation.error.message}</p>}
            {workspaceMutation.data?.username === clientId && (
              <p className="settings-success">当前用户：{clientId}</p>
            )}
            <button className="section-action" disabled={workspaceMutation.isPending}>
              {workspaceMutation.isPending ? "切换中…" : "打开或创建用户"}
            </button>
          </form>
        </details>

        <details className="settings-section" open>
          <summary>
            <span><Bot size={14} />Codex CLI</span>
            <small>{codexQuery.data?.authenticated ? "已登录" : "未连接"}</small>
            <ChevronDown size={14} />
          </summary>
          <div className="codex-status">
            {codexQuery.isLoading && <p className="inspector-muted">正在读取 Server 上的 Codex 状态…</p>}
            {codexQuery.error && <p className="form-error">无法读取 Codex 状态：{codexQuery.error.message}</p>}
            {codexQuery.data && !codexQuery.data.authenticated && (
              <p className="settings-note">请在 Server 主机运行 codex login，完成后刷新状态。</p>
            )}
            {codexQuery.data?.authenticated && (
              <p className="settings-success">
                已通过 {codexQuery.data.auth_mode} 登录{codexQuery.data.plan_type ? ` · ${codexQuery.data.plan_type}` : ""}
              </p>
            )}
            {codexQuery.data?.windows.map((window) => (
              <div className="limit-row" key={window.name}>
                <p><span>{limitLabel(window.window_minutes)}</span><b>剩余 {remainingPercent(window.used_percent)}%</b></p>
                <progress aria-label={limitLabel(window.window_minutes)} max={100} value={remainingPercent(window.used_percent)} />
                <small>{window.resets_at ? `${new Date(window.resets_at * 1000).toLocaleString("zh-CN")} 重置` : "重置时间不可用"}</small>
              </div>
            ))}
          </div>
        </details>
        <details className="settings-section" open>
          <summary><span><ServerCog size={14} />模型运行时</span><small>{provider}</small><ChevronDown size={14} /></summary>
          <form onSubmit={submitConfig}>
            <p className="settings-note">配置立即用于当前用户的 Native Agent，Server 重启后恢复环境变量配置。</p>
            <label>
              Provider
              <select
                aria-label="Provider"
                disabled={providersQuery.isLoading || configQuery.isLoading}
                value={provider}
                onChange={(event) => selectProvider(event.target.value)}
              >
                {providersQuery.data?.map((item) => (
                  <option key={item.provider} value={item.provider}>{item.display_name}</option>
                ))}
              </select>
            </label>
            <label>
              Model
              <select aria-label="Model" disabled={!selected} value={model} onChange={(event) => setModel(event.target.value)}>
                {selected?.models.map((item) => (
                  <option key={item.model} value={item.model}>{item.display_name}</option>
                ))}
              </select>
            </label>
            {provider !== "mock" && (
              <label>
                API Key（留空则使用 Server 环境变量）
                <span className="secret-input"><KeyRound size={14} /><input name="api_key" type="password" autoComplete="off" /></span>
              </label>
            )}
            {configQuery.isLoading && <p className="inspector-muted">正在读取当前配置…</p>}
            {providersQuery.error && <p className="form-error">{providersQuery.error.message}</p>}
            {configMutation.error && <p className="form-error">{configMutation.error.message}</p>}
            {configured && (
              <p className="settings-success">
                当前配置：{configured.provider} / {configured.model} · Key 来源：{configured.api_key_source}
              </p>
            )}
            <p className="inspector-muted">API Key 按用户与厂商加密保存在本地 Server，不会回显。</p>
            <button className="section-action" disabled={!selected || configMutation.isPending}>
              {configMutation.isPending ? "应用中…" : "应用配置"}
            </button>
          </form>
        </details>

        <div className="modal-actions"><button type="button" onClick={onClose}>关闭</button></div>
      </div>
    </div>
  );
}
