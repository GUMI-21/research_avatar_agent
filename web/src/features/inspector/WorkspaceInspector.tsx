import {
  Activity,
  Bot,
  CircleDollarSign,
  Clock3,
  Database,
  Gauge,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { MemoryPanel } from "../memory/MemoryPanel";

import {
  Agent,
  RunUsage,
  UsageSummary,
  WorkspaceSession,
  workspaceApi,
} from "../../shared/api/workspace";

type InspectorTab = "agent" | "memory" | "run" | "usage";

type Props = {
  agent?: Agent;
  session?: WorkspaceSession;
  sessions: WorkspaceSession[];
  messageCount: number;
  runs: RunUsage[];
  summary?: UsageSummary;
  loading: boolean;
};

const statusLabels: Record<RunUsage["status"], string> = {
  pending: "等待中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

function number(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function duration(value: number | null) {
  if (value == null) return "—";
  return value < 1_000 ? `${value} ms` : `${(value / 1_000).toFixed(2)} s`;
}

function codexWindowLabel(minutes: number | null) {
  if (minutes === 300) return "5 小时";
  if (minutes === 10080) return "周";
  return minutes ? `${minutes} 分钟` : "额度";
}
function cost(value: string | null) {
  return value == null ? "不可用" : `$${Number(value).toFixed(6)}`;
}

export function WorkspaceInspector({
  agent,
  session,
  sessions,
  messageCount,
  runs,
  summary,
  loading,
}: Props) {
  const [tab, setTab] = useState<InspectorTab>("agent");
  const showCodexUsage = agent?.runtime === "codex" && tab === "usage";
  const codexStatusQuery = useQuery({
    queryKey: ["codex-status"],
    queryFn: workspaceApi.getCodexStatus,
    enabled: showCodexUsage,
    refetchInterval: showCodexUsage ? 60_000 : false,
  });
  const sessionRuns = useMemo(
    () => runs.filter((run) => run.session_id === session?.id),
    [runs, session?.id],
  );
  const sessionUsage = useMemo(() => ({
    runCount: sessionRuns.length,
    inputTokens: sessionRuns.reduce((total, run) => total + (run.input_tokens ?? 0), 0),
    outputTokens: sessionRuns.reduce((total, run) => total + (run.output_tokens ?? 0), 0),
    cost: sessionRuns.reduce((total, run) => total + Number(run.cost_usd ?? 0), 0),
  }), [sessionRuns]);

  return (
    <aside className="inspector">
      <div className="inspector-tabs">
        {(["agent", "memory", "run", "usage"] as const).map((name) => (
          <button className={tab === name ? "active" : ""} key={name} onClick={() => setTab(name)}>
            {{ agent: "Agent", memory: "Memory", run: "Run", usage: "Usage" }[name]}
          </button>
        ))}
      </div>

      {tab === "agent" && (agent ? (
        <>
          <section>
            <h2><Bot size={15} />当前 Agent</h2>
            <div className="profile-card">
              <span className="avatar large">{agent.avatar_emoji || agent.name.trim().charAt(0).toUpperCase()}</span>
              <div><b>{agent.name}</b><small>{agent.runtime === "codex" ? `Codex CLI · ${agent.workspace_path || "默认目录"}` : `${agent.runtime} · ${agent.model || "默认模型"}`}</small></div>
            </div>
          </section>
          <section>
            <h2><Sparkles size={15} />{agent.runtime === "codex" ? "服务端项目" : "System Prompt"}</h2>
            <p className="reason">{agent.runtime === "codex" ? agent.workspace_path || "默认目录" : agent.system_prompt}</p>
          </section>
          <section>
            <h2><Database size={15} />工作区数据</h2>
            <dl className="metrics">
              <div><dt>会话</dt><dd>{sessions.filter((item) => item.agent_id === agent.id).length}</dd></div>
              <div><dt>知识库</dt><dd>{agent.knowledge_source_ids.length}</dd></div>
              <div><dt>当前消息</dt><dd>{messageCount}</dd></div>
            </dl>
          </section>
        </>
      ) : <InspectorEmpty text="选择 Agent 查看配置" />)}

      {tab === "memory" && (
        agent ? <MemoryPanel agentId={agent.id} /> : <InspectorEmpty text="选择 Agent 管理记忆" />
      )}

      {tab === "run" && (
        <section>
          <h2><Activity size={15} />当前会话 Runs</h2>
          {loading ? <p className="inspector-muted">正在读取运行记录…</p>
            : !session ? <InspectorEmpty text="选择会话查看运行记录" />
            : !sessionRuns.length ? <InspectorEmpty text="当前会话还没有运行记录" />
            : sessionRuns.map((run) => <RunUsageCard key={run.id} run={run} />)}
        </section>
      )}

      {tab === "usage" && (
        <>
          <section>
            <h2><Gauge size={15} />当前会话</h2>
            <dl className="metrics usage-grid">
              <div><dt>Runs</dt><dd>{sessionUsage.runCount}</dd></div>
              <div><dt>输入 Tokens</dt><dd>{number(sessionUsage.inputTokens)}</dd></div>
              <div><dt>输出 Tokens</dt><dd>{number(sessionUsage.outputTokens)}</dd></div>
              <div><dt>估算费用</dt><dd>${sessionUsage.cost.toFixed(6)}</dd></div>
            </dl>
          </section>
          {agent?.runtime === "codex" && (
            <section>
              <h2><Gauge size={15} />Codex 剩余额度</h2>
              {codexStatusQuery.isLoading && <p className="inspector-muted">正在读取 Codex 额度…</p>}
              {codexStatusQuery.error && <p className="form-error">Codex 额度暂不可用</p>}
              {codexStatusQuery.data && !codexStatusQuery.data.authenticated && (
                <p className="inspector-muted">Server Codex CLI 未登录</p>
              )}
              {codexStatusQuery.data?.windows.map((window) => {
                const remaining = Math.max(0, Math.min(100, 100 - window.used_percent));
                return (
                  <div className="limit-row" key={window.name}>
                    <p><span>{codexWindowLabel(window.window_minutes)}额度</span><b>剩余 {remaining}%</b></p>
                    <progress aria-label={`${codexWindowLabel(window.window_minutes)}剩余额度`} max={100} value={remaining} />
                    <small>{window.resets_at ? `${new Date(window.resets_at * 1000).toLocaleString("zh-CN")} 重置` : "重置时间不可用"}</small>
                  </div>
                );
              })}
            </section>
          )}
          <section>
            <h2><CircleDollarSign size={15} />Workspace 总计</h2>
            {summary ? (
              <dl className="metrics usage-grid">
                <div><dt>Runs / 失败</dt><dd>{summary.run_count} / {summary.failed_count}</dd></div>
                <div><dt>输入 Tokens</dt><dd>{number(summary.input_tokens)}</dd></div>
                <div><dt>输出 Tokens</dt><dd>{number(summary.output_tokens)}</dd></div>
                <div><dt>估算费用</dt><dd>${Number(summary.cost_usd).toFixed(6)}</dd></div>
                <div><dt>平均耗时</dt><dd>{duration(summary.average_duration_ms)}</dd></div>
                <div><dt>费用不可用</dt><dd>{summary.unavailable_cost_count}</dd></div>
              </dl>
            ) : <p className="inspector-muted">用量汇总暂不可用</p>}
          </section>
        </>
      )}
    </aside>
  );
}

function RunUsageCard({ run }: { run: RunUsage }) {
  const failed = run.status === "failed" || run.status === "cancelled";
  return (
    <article className="usage-card">
      <div className="usage-card-title">
        <b>{run.model || run.runtime}</b>
        <span className={failed ? "failed" : run.status}>{statusLabels[run.status]}</span>
      </div>
      <p>{run.provider || "provider 未记录"} · {new Date(run.created_at).toLocaleString("zh-CN")}</p>
      <dl>
        <div><dt>Tokens</dt><dd>{number(run.input_tokens ?? 0)} / {number(run.output_tokens ?? 0)}</dd></div>
        <div><dt><CircleDollarSign size={11} />费用</dt><dd>{cost(run.cost_usd)} <small>{run.cost_status}</small></dd></div>
        <div><dt><Clock3 size={11} />耗时 / 首 Token</dt><dd>{duration(run.duration_ms)} / {duration(run.time_to_first_token_ms)}</dd></div>
        {run.error_type && <div className="run-error"><dt><TriangleAlert size={11} />错误</dt><dd>{run.error_type}</dd></div>}
      </dl>
    </article>
  );
}

function InspectorEmpty({ text }: { text: string }) {
  return <div className="inspector-empty"><Bot size={24} /><span>{text}</span></div>;
}
