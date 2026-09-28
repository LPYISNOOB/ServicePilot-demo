import { FormEvent, useMemo, useState } from "react";
import { AgentResponse, sendMessage, submitApproval } from "./api";

type ChatItem = { role: "user" | "assistant"; content: string };

const EXAMPLES = [
  "这个订单的充电器有问题，我想退款 299 元",
  "查询这个订单的物流状态",
  "收到的商品破损了，我需要怎么处理？",
  "我要找律师起诉你们",
];

function App() {
  const [email, setEmail] = useState("zhangwei@example.com");
  const [orderId, setOrderId] = useState("SP-2026-0001");
  const [reviewer, setReviewer] = useState("demo-manager");
  const [message, setMessage] = useState(EXAMPLES[0]);
  const [threadId, setThreadId] = useState<string>();
  const [chat, setChat] = useState<ChatItem[]>([]);
  const [latest, setLatest] = useState<AgentResponse>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [comment, setComment] = useState("已核对订单、退款金额和政策依据");

  const pending = latest?.status === "pending_approval";
  const riskClass = useMemo(() => `risk risk-${latest?.risk_level || "none"}`, [latest?.risk_level]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!message.trim() || loading || pending) return;
    const text = message.trim();
    setChat((items) => [...items, { role: "user", content: text }]);
    setLoading(true);
    setError("");
    try {
      const result = await sendMessage({
        message: text,
        customer_email: email,
        order_id: orderId,
        thread_id: threadId,
      });
      setThreadId(result.thread_id);
      setLatest(result);
      if (result.answer) setChat((items) => [...items, { role: "assistant", content: result.answer }]);
      setMessage("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "请求失败");
    } finally {
      setLoading(false);
    }
  }

  async function decide(approved: boolean) {
    if (!threadId || loading) return;
    setLoading(true);
    setError("");
    try {
      const result = await submitApproval(threadId, { approved, reviewer, comment });
      setLatest(result);
      if (result.answer) setChat((items) => [...items, { role: "assistant", content: result.answer }]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "审批失败");
    } finally {
      setLoading(false);
    }
  }

  function newConversation() {
    setThreadId(undefined);
    setLatest(undefined);
    setChat([]);
    setError("");
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">S</div>
          <div><h1>ServicePilot</h1><p>Enterprise After-sales Intelligence</p></div>
        </div>
        <div className="top-actions">
          <span className="live-dot" /> Mock mode · Local safe
          <button className="ghost" onClick={newConversation}>新建会话</button>
        </div>
      </header>

      <section className="workspace">
        <aside className="identity-panel card">
          <div className="section-kicker">CUSTOMER CONTEXT</div>
          <h2>客户身份</h2>
          <label>下单邮箱<input value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <label>订单号<input value={orderId} onChange={(e) => setOrderId(e.target.value.toUpperCase())} /></label>
          <div className="verified"><span>✓</span><div><b>演示数据</b><small>身份由后端按订单归属核验</small></div></div>
          <div className="divider" />
          <div className="section-kicker">QUICK SCENARIOS</div>
          <div className="scenario-list">
            {EXAMPLES.map((example, index) => (
              <button key={example} onClick={() => setMessage(example)}>
                <span>0{index + 1}</span>{example}
              </button>
            ))}
          </div>
        </aside>

        <section className="conversation card">
          <div className="conversation-head">
            <div><div className="section-kicker">AGENT WORKSPACE</div><h2>售后协作会话</h2></div>
            <span className={riskClass}>{latest?.risk_level ? `${latest.risk_level} risk` : "waiting"}</span>
          </div>
          <div className="messages">
            {chat.length === 0 && (
              <div className="empty-state"><div>⌁</div><h3>让多个专业 Agent 开始协作</h3><p>系统会核验订单、检索生效政策、评估风险，并在写操作前等待你的审批。</p></div>
            )}
            {chat.map((item, index) => (
              <div className={`message ${item.role}`} key={`${item.role}-${index}`}>
                <span>{item.role === "user" ? "客户" : "AI"}</span><p>{item.content}</p>
              </div>
            ))}
            {loading && <div className="agent-thinking"><i /><i /><i /> Supervisor 正在调度专业 Agent</div>}
          </div>
          {error && <div className="error-banner">{error}</div>}
          <form className="composer" onSubmit={onSubmit}>
            <textarea value={message} onChange={(e) => setMessage(e.target.value)} disabled={pending} placeholder={pending ? "请先完成右侧人工审批" : "输入客户问题……"} />
            <button disabled={loading || pending || !message.trim()}>{loading ? "处理中" : "发送 →"}</button>
          </form>
        </section>

        <aside className="inspector card">
          {pending ? (
            <div className="approval-box">
              <div className="approval-icon">!</div>
              <div className="section-kicker">HUMAN APPROVAL</div>
              <h2>需要人工决策</h2>
              <p>工作流已安全暂停，批准前不会执行退款或其他业务写操作。</p>
              <pre>{JSON.stringify(latest?.pending_approval, null, 2)}</pre>
              <label>审批人<input value={reviewer} onChange={(e) => setReviewer(e.target.value)} /></label>
              <label>备注<textarea value={comment} onChange={(e) => setComment(e.target.value)} /></label>
              <div className="approval-actions"><button className="reject" onClick={() => decide(false)}>拒绝</button><button className="approve" onClick={() => decide(true)}>批准并继续</button></div>
            </div>
          ) : (
            <>
              <div className="section-kicker">OBSERVABILITY</div><h2>运行上下文</h2>
              <dl className="facts"><div><dt>Ticket</dt><dd>{latest?.ticket_id || "—"}</dd></div><div><dt>Intent</dt><dd>{latest?.intent || "—"}</dd></div><div><dt>Evidence</dt><dd>{latest?.evidence.length ?? 0}</dd></div></dl>
              <div className="divider" />
              <h3>Agent 轨迹</h3>
              <ol className="timeline">
                {(latest?.route_log ?? []).map((step, index) => <li key={`${step}-${index}`}><span>{index + 1}</span>{step}</li>)}
              </ol>
              <div className="divider" />
              <h3>政策证据</h3>
              <div className="evidence-list">
                {(latest?.evidence ?? []).map((item) => <article key={item.document_id}><b>{item.title}</b><small>v{item.version} · score {item.score.toFixed(3)}</small><p>{item.snippet.slice(0, 100)}…</p></article>)}
              </div>
            </>
          )}
        </aside>
      </section>
    </main>
  );
}

export default App;

