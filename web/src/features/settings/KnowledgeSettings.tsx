import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";

import { Agent, workspaceApi } from "../../shared/api/workspace";

type Props = { agents: Agent[]; onAgentUpdated: (agent: Agent) => void };

export function KnowledgeSettings({ agents, onAgentUpdated }: Props) {
  const queryClient = useQueryClient();
  const sourcesQuery = useQuery({ queryKey: ["knowledge-sources"], queryFn: workspaceApi.listKnowledgeSources });
  const nativeAgents = agents.filter((agent) => agent.runtime === "native");
  const [agentId, setAgentId] = useState(nativeAgents[0]?.id || "");
  const agent = nativeAgents.find((item) => item.id === agentId);
  useEffect(() => {
    if (!agentId && nativeAgents[0]) setAgentId(nativeAgents[0].id);
  }, [agentId, nativeAgents]);
  const createMutation = useMutation({
    mutationFn: workspaceApi.createKnowledgeSource,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-sources"] }),
  });
  const actionMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "sync" | "index" }) =>
      action === "sync" ? workspaceApi.syncKnowledgeSource(id) : workspaceApi.indexKnowledgeSource(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-sources"] }),
  });
  const bindingMutation = useMutation({
    mutationFn: ({ id, sourceIds }: { id: string; sourceIds: string[] }) =>
      workspaceApi.updateAgentKnowledgeSources(id, sourceIds),
    onSuccess: onAgentUpdated,
  });
  function createSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    createMutation.mutate({
      name: String(data.get("name")), root_path: String(data.get("root_path")),
      source_type: String(data.get("source_type")) as "obsidian" | "markdown",
    }, { onSuccess: () => form.reset() });
  }
  return (
    <div className="knowledge-settings">
      <p className="settings-note">目录路径位于 Server 主机。先同步 Markdown，再生成向量索引并绑定到 Native Agent。</p>
      <form className="knowledge-create" onSubmit={createSource}>
        <label>名称<input name="name" required maxLength={120} placeholder="例如：Obsidian Vault" /></label>
        <label>Server 目录<input name="root_path" required maxLength={2048} placeholder="D:\Notes\Vault" /></label>
        <label>类型<select name="source_type" defaultValue="obsidian"><option value="obsidian">Obsidian</option><option value="markdown">Markdown</option></select></label>
        <button className="section-action" disabled={createMutation.isPending}>添加目录</button>
      </form>
      {(createMutation.error || actionMutation.error || bindingMutation.error) && (
        <p className="form-error">{(createMutation.error || actionMutation.error || bindingMutation.error)?.message}</p>
      )}
      <div className="knowledge-list">
        {sourcesQuery.data?.map((source) => (
          <article key={source.id}>
            <div><b>{source.name}</b><span className={source.sync_status}>{source.sync_status}</span></div>
            <p title={source.root_path}>{source.root_path}</p>
            <small>{source.last_synced_at ? `同步于 ${new Date(source.last_synced_at).toLocaleString("zh-CN")}` : "尚未同步"}</small>
            <div className="knowledge-actions">
              <button aria-label={`同步 ${source.name}`} disabled={actionMutation.isPending} onClick={() => actionMutation.mutate({ id: source.id, action: "sync" })}>同步</button>
              <button aria-label={`向量化 ${source.name}`} disabled={actionMutation.isPending || source.sync_status !== "ready"} onClick={() => actionMutation.mutate({ id: source.id, action: "index" })}>向量化</button>
            </div>
          </article>
        ))}
      </div>
      <label>绑定 Agent<select aria-label="知识库 Agent" value={agentId} onChange={(event) => setAgentId(event.target.value)}>{nativeAgents.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      {sourcesQuery.data?.map((source) => {
        const enabled = agent?.knowledge_source_ids.includes(source.id) ?? false;
        return <label className="knowledge-binding" key={source.id}><input aria-label={`绑定 ${source.name}`} type="checkbox" checked={enabled} disabled={!agent || bindingMutation.isPending} onChange={() => agent && bindingMutation.mutate({ id: agent.id, sourceIds: enabled ? agent.knowledge_source_ids.filter((id) => id !== source.id) : [...agent.knowledge_source_ids, source.id] })} /><span>{source.name}</span></label>;
      })}
    </div>
  );
}
