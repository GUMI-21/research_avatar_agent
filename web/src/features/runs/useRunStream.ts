import { useCallback, useEffect, useRef, useState } from "react";

import {
  RunEventFrame,
  SocketState,
  WorkspaceFrame,
  WorkspaceRunSocket,
} from "../../shared/api/runSocket";

const terminalEvents = new Set(["run_finished", "run_failed", "run_cancelled"]);

export type PendingApproval = {
  id: string;
  toolName: string;
  path: string;
  contentPreview: string;
};

export type LiveRun = {
  sessionId: string | null;
  runId: string | null;
  userText: string;
  assistantText: string;
  events: RunEventFrame[];
  status: "idle" | "running" | "completed" | "failed" | "cancelled";
  error: string | null;
  approval: PendingApproval | null;
};

const emptyRun: LiveRun = {
  sessionId: null,
  runId: null,
  userText: "",
  assistantText: "",
  events: [],
  status: "idle",
  error: null,
  approval: null,
};

export function useRunStream(
  clientId: string,
  onTerminal: (runId: string, sessionId: string) => void,
) {
  const [connection, setConnection] = useState<SocketState>("connecting");
  const [run, setRun] = useState<LiveRun>(emptyRun);
  const clientRef = useRef<WorkspaceRunSocket | null>(null);
  const activeSessionRef = useRef("");
  const terminalRef = useRef(onTerminal);
  terminalRef.current = onTerminal;

  useEffect(() => {
    setRun(emptyRun);
    activeSessionRef.current = "";
    const client = new WorkspaceRunSocket(clientId, (frame) => {
      handleFrame(frame, setRun, terminalRef.current, activeSessionRef.current);
    }, setConnection);
    clientRef.current = client;
    client.connect();
    return () => client.close();
  }, [clientId]);

  const send = useCallback((sessionId: string, content: string, targetAgentId?: string) => {
    activeSessionRef.current = sessionId;
    setRun({ ...emptyRun, sessionId, userText: content, status: "running" });
    try {
      clientRef.current?.sendMessage(sessionId, content, targetAgentId);
    } catch (error) {
      setRun((current) => ({
        ...current,
        status: "failed",
        error: error instanceof Error ? error.message : "发送失败",
      }));
    }
  }, []);

  const approve = useCallback((approved: boolean) => {
    if (!run.runId || !run.approval) return;
    clientRef.current?.approve(run.runId, run.approval.id, approved);
    setRun((current) => ({ ...current, approval: null }));
  }, [run.runId, run.approval]);
  const cancel = useCallback(() => {
    if (run.runId) clientRef.current?.cancel(run.runId);
  }, [run.runId]);

  return { connection, run, send, approve, cancel };
}

function handleFrame(
  frame: WorkspaceFrame,
  setRun: React.Dispatch<React.SetStateAction<LiveRun>>,
  onTerminal: (runId: string, sessionId: string) => void,
  sessionId: string,
) {
  if (frame.type === "error") {
    setRun((current) => ({ ...current, status: "failed", error: frame.message }));
    return;
  }
  if (frame.type === "replay_complete") return;
  setRun((current) => ({
    ...current,
    runId: frame.run_id,
    assistantText: frame.type === "assistant_delta"
      ? current.assistantText + String(frame.payload.text ?? "")
      : current.assistantText,
    events: frame.type === "assistant_delta" ? current.events : [...current.events, frame],
    approval: frame.type === "approval_required" ? {
      id: String(frame.payload.approval_id),
      toolName: String(frame.payload.tool_name),
      path: String(frame.payload.path ?? ""),
      contentPreview: String(frame.payload.content_preview ?? ""),
    } : frame.type === "tool_finished" ? null : current.approval,
    status: frame.type === "run_finished" ? "completed"
      : frame.type === "run_failed" ? "failed"
      : frame.type === "run_cancelled" ? "cancelled"
      : current.status,
  }));
  if (terminalEvents.has(frame.type)) onTerminal(frame.run_id, sessionId);
}
