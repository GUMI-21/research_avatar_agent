import { useMutation, useQuery } from "@tanstack/react-query";
import { KeyRound, ServerCog, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { LLMConfigResponse, workspaceApi } from "../../shared/api/workspace";

type Props = {
  onClose: () => void;
};

export function WorkspaceSettings({ onClose }: Props) {
  const providersQuery = useQuery({
    queryKey: ["llm-providers"],
    queryFn: workspaceApi.listLLMProviders,
  });
  const configQuery = useQuery({
    queryKey: ["llm-config"],
    queryFn: workspaceApi.getLLMConfig,
  });
  const [provider, setProvider] = useState("mock");
  const [model, setModel] = useState("mock-echo");
  const [configured, setConfigured] = useState<LLMConfigResponse>();
  const selected = providersQuery.data?.find((item) => item.provider === provider);
  const mutation = useMutation({
    mutationFn: workspaceApi.configureLLM,
    onSuccess: setConfigured,
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

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const apiKey = String(data.get("api_key") || "").trim();
    mutation.mutate({
      provider,
      model,
      ...(apiKey ? { api_key: apiKey } : {}),
    });
  }

  return (
    <div className="modal-backdrop">
      <form className="modal settings-modal" onSubmit={submit}>
        <div className="modal-title">
          <div><small>RUNTIME SETTINGS</small><h2>模型设置</h2></div>
          <button type="button" aria-label="关闭" onClick={onClose}><X size={18} /></button>
        </div>
        <p className="settings-note">
          <ServerCog size={14} />此配置会立即用于 Native Agent，并在 Server 重启后恢复环境变量配置。
        </p>
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
          <select
            aria-label="Model"
            disabled={!selected}
            value={model}
            onChange={(event) => setModel(event.target.value)}
          >
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
        {mutation.error && <p className="form-error">{mutation.error.message}</p>}
        {configured && (
          <p className="settings-success">
            当前配置：{configured.provider} / {configured.model} · Key 来源：{configured.api_key_source}
          </p>
        )}
        <div className="modal-actions">
          <button type="button" onClick={onClose}>关闭</button>
          <button className="primary" disabled={!selected || mutation.isPending}>
            {mutation.isPending ? "应用中…" : "应用配置"}
          </button>
        </div>
      </form>
    </div>
  );
}
