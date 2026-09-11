import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, MemoryStick, Plus, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";

import { workspaceApi } from "../../shared/api/workspace";

export function MemoryPanel({ agentId }: { agentId: string }) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const queryKey = ["memories", agentId];
  const memories = useQuery({
    queryKey,
    queryFn: () => workspaceApi.listMemories(agentId),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey });
  const create = useMutation({
    mutationFn: (value: string) => workspaceApi.createMemory(agentId, value),
    onSuccess: () => { setContent(""); void refresh(); },
  });
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      workspaceApi.updateMemory(agentId, id, enabled),
    onSuccess: () => void refresh(),
  });
  const remove = useMutation({
    mutationFn: (id: string) => workspaceApi.deleteMemory(agentId, id),
    onSuccess: () => void refresh(),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = content.trim();
    if (value) create.mutate(value);
  }

  const error = memories.error || create.error || toggle.error || remove.error;
  return (
    <section className="memory-panel">
      <h2><MemoryStick size={15} />长期记忆</h2>
      <p className="inspector-muted">启用的内容会按预算加入该 Agent 的上下文。</p>
      <form onSubmit={submit}>
        <textarea
          aria-label="新增长期记忆"
          maxLength={4000}
          placeholder="例如：回答时优先使用简洁中文"
          value={content}
          onChange={(event) => setContent(event.target.value)}
        />
        <button disabled={!content.trim() || create.isPending}>
          <Plus size={13} />添加记忆
        </button>
      </form>
      {error && <p className="form-error">{error.message}</p>}
      {memories.isLoading && <LoaderCircle className="spinner" />}
      <div className="memory-list">
        {memories.data?.map((memory) => (
          <article className={memory.enabled ? "" : "disabled"} key={memory.id}>
            <p>{memory.content}</p>
            <div>
              <label>
                <input
                  aria-label={`${memory.enabled ? "禁用" : "启用"}记忆`}
                  type="checkbox"
                  checked={memory.enabled}
                  onChange={() => toggle.mutate({ id: memory.id, enabled: !memory.enabled })}
                />
                {memory.enabled ? "已启用" : "已禁用"}
              </label>
              <button aria-label="删除记忆" onClick={() => remove.mutate(memory.id)}>
                <Trash2 size={13} />
              </button>
            </div>
          </article>
        ))}
        {!memories.isLoading && !memories.data?.length && (
          <div className="inspector-empty"><MemoryStick size={23} /><span>还没有长期记忆</span></div>
        )}
      </div>
    </section>
  );
}
