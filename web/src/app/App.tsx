import {
  Bot,
  BrainCircuit,
  CircleDollarSign,
  Database,
  FileText,
  Plus,
  Search,
  Send,
  Settings,
  Sparkles,
} from "lucide-react";

const sessions = ["RAG 技术方案", "本周开发计划", "论文阅读助手"];
const events = [
  ["Retrieval", "检索到 4 个知识片段", "38 ms"],
  ["Context", "注入 2,840 tokens", "12 ms"],
  ["Native Agent", "正在生成回答", "1.4 s"],
];

export function App() {
  return (
    <main className="workspace-shell">
      <aside className="sidebar">
        <div className="brand"><BrainCircuit size={20} /><span>Agent Workspace</span></div>
        <button className="new-session"><Plus size={16} />新建对话</button>
        <p className="section-label">AGENTS</p>
        <button className="agent active"><span className="avatar">P</span><span><b>Personal</b><small>Native · 在线</small></span></button>
        <button className="agent"><span className="avatar muted">C</span><span><b>Coder</b><small>Codex · 待接入</small></span></button>
        <p className="section-label">RECENT SESSIONS</p>
        <nav className="sessions">
          {sessions.map((session, index) => <button className={index === 0 ? "active" : ""} key={session}><FileText size={14} />{session}</button>)}
        </nav>
        <button className="settings"><Settings size={15} />设置</button>
      </aside>

      <section className="conversation">
        <header className="conversation-header">
          <div><h1>RAG 技术方案</h1><p><span className="status-dot" /> Personal Agent · gpt-5.6-luna</p></div>
          <button className="icon-button" aria-label="搜索"><Search size={17} /></button>
        </header>
        <div className="messages">
          <article className="message user-message">结合我的 Obsidian 笔记，解释一下混合检索应该怎么实现？</article>
          <article className="run-card">
            <div className="run-card-title"><Sparkles size={16} /><b>Personal Agent</b><span>运行完成</span></div>
            {events.map(([name, detail, time]) => (
              <div className="run-event" key={name}><span className="event-dot" /><b>{name}</b><span>{detail}</span><time>{time}</time></div>
            ))}
          </article>
          <article className="message assistant-message">
            <p>你的知识库适合采用两路检索：FTS5 负责中文关键词和专有名词，向量检索负责语义相似内容。两路结果经过加权、去重后，再组装成带引用的上下文。</p>
            <div className="citations"><span>[1] RAG/混合检索.md</span><span>[2] Notes/Embedding.md</span></div>
          </article>
        </div>
        <form className="composer">
          <textarea aria-label="消息" placeholder="向 Personal Agent 提问，或使用 @Coder 委派任务…" />
          <div><span>Enter 发送 · Shift+Enter 换行</span><button type="button" aria-label="发送"><Send size={17} /></button></div>
        </form>
      </section>

      <aside className="inspector">
        <div className="inspector-tabs"><button className="active">Context</button><button>Run</button><button>Usage</button></div>
        <section><h2><Database size={15} />检索上下文</h2><div className="context-card"><b>RAG/混合检索.md</b><p>关键词召回与向量召回需要独立打分，合并后进行去重和重排……</p><span>score 0.91 · chunk 3</span></div><div className="context-card"><b>Notes/Embedding.md</b><p>中文笔记应保留标题层级作为 chunk 元数据……</p><span>score 0.84 · chunk 7</span></div></section>
        <section><h2><Bot size={15} />为什么选择 Agent</h2><p className="reason">任务需要读取个人知识库，继续由具备 RAG 权限的 Personal Agent 执行。</p></section>
        <section><h2><CircleDollarSign size={15} />本次运行</h2><dl className="metrics"><div><dt>Tokens</dt><dd>2,840 / 426</dd></div><div><dt>Cost</dt><dd>$0.0011 <small>estimated</small></dd></div><div><dt>Latency</dt><dd>1.45 s</dd></div></dl></section>
      </aside>
    </main>
  );
}
