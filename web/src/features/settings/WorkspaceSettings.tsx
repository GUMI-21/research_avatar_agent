import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronDown, KeyRound, ServerCog, UserRound, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { LLMConfigResponse, workspaceApi } from "../../shared/api/workspace";

type Props = {
  clientId: string;
  onClose: () => void;
  onWorkspaceChange: (clientId: string) => Promise<void>;
};

export function WorkspaceSettings({ clientId, onClose, onWorkspaceChange }: Props) {
  const providersQuery = useQuery({
    queryKey: ["llm-providers"],
    queryFn: workspaceApi.listLLMProviders,
  });
  const configQuery = useQuery({
    queryKey: ["llm-config", clientId],
    queryFn: workspaceApi.getLLMConfig,
  });
  const [provider, setProvider] = useState("mock");
  const [model, setModel] = useState("mock-echo");
  const [username, setUsername] = useState(clientId);
  const [configured, setConfigured] = useState<LLMConfigResponse>();
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

  useEffect(() => {
    if (!configQuery.data) return;
    setProvider(configQuery.data.provider);
    setModel(configQuery.data.model);
    setConfigured(configQuery.data);
  }, [configQuery.data]);

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
