export type SocketState = "connecting" | "open" | "closed";

export type RunEventType =
  | "run_started" | "run_finished" | "run_failed" | "run_cancelled"
  | "agent_started" | "agent_status"
  | "retrieval_started" | "retrieval_result" | "context_prepared"
  | "tool_started" | "tool_finished"
  | "handoff_requested" | "handoff_started" | "handoff_finished"
  | "usage_updated" | "assistant_delta" | "approval_required" | "provider_retry";

export type RunEventFrame = {
  type: RunEventType;
  run_id: string;
  sequence: number | null;
  payload: Record<string, unknown>;
};

export type WorkspaceFrame = RunEventFrame | {
  type: "error";
  code: string;
  message: string;
} | {
  type: "replay_complete";
  run_id: string;
  last_sequence: number;
  count: number;
  has_more: boolean;
};

const terminalEvents = new Set(["run_finished", "run_failed", "run_cancelled"]);

export class WorkspaceRunSocket {
  private socket: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private stopped = false;
  private activeRunId: string | null = null;
  private lastSequence = 0;

  constructor(
    private readonly clientId: string,
    private readonly onFrame: (frame: WorkspaceFrame) => void,
    private readonly onState: (state: SocketState) => void,
  ) {}

  connect() {
    this.stopped = false;
    this.onState("connecting");
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    this.socket = new WebSocket(
      `${protocol}//${window.location.host}/api/v1/ws?client_id=${encodeURIComponent(this.clientId)}`,
    );
    this.socket.onopen = () => {
      this.onState("open");
      if (this.activeRunId) this.resume();
    };
    this.socket.onmessage = (message) => this.receive(String(message.data));
    this.socket.onclose = () => {
      this.onState("closed");
      if (!this.stopped) {
        this.reconnectTimer = window.setTimeout(() => this.connect(), 1_000);
      }
    };
  }

  sendMessage(sessionId: string, content: string, targetAgentId?: string) {
    this.activeRunId = null;
    this.lastSequence = 0;
    this.send({
      type: "send_message",
      session_id: sessionId,
      content,
      ...(targetAgentId ? { target_agent_id: targetAgentId } : {}),
    });
  }

  approve(runId: string, approvalId: string, approved: boolean) {
    this.send({ type: "tool_approval", run_id: runId, approval_id: approvalId, approved });
  }

  cancel(runId: string) {
    this.send({ type: "cancel_run", run_id: runId });
  }

  close() {
    this.stopped = true;
    if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer);
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
    }
  }

  private send(command: Record<string, unknown>) {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      throw new Error("实时连接尚未就绪");
    }
    this.socket.send(JSON.stringify(command));
  }

  private resume() {
    this.send({
      type: "resume_run",
      run_id: this.activeRunId,
      after_sequence: this.lastSequence,
      limit: 100,
    });
  }

  private receive(raw: string) {
    let frame: WorkspaceFrame;
    try {
      frame = JSON.parse(raw) as WorkspaceFrame;
    } catch {
      this.onFrame({ type: "error", code: "invalid_frame", message: "服务端返回了无效事件" });
      return;
    }
    if ("run_id" in frame && frame.type !== "replay_complete") {
      this.activeRunId = frame.run_id;
      if (frame.sequence !== null) this.lastSequence = Math.max(this.lastSequence, frame.sequence);
      if (terminalEvents.has(frame.type)) this.activeRunId = null;
    }
    this.onFrame(frame);
    if (frame.type === "replay_complete" && frame.has_more) {
      this.lastSequence = frame.last_sequence;
      this.resume();
    }
  }
}
