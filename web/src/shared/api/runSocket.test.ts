import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkspaceRunSocket } from "./runSocket";

class FakeWebSocket {
  static OPEN = 1;
  static instances: FakeWebSocket[] = [];
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(readonly url: string) { FakeWebSocket.instances.push(this); }
  open() { this.readyState = FakeWebSocket.OPEN; this.onopen?.(); }
  send(data: string) { this.sent.push(data); }
  close() { this.readyState = 3; this.onclose?.(); }
  disconnect() { this.readyState = 3; this.onclose?.(); }
  emit(frame: object) { this.onmessage?.({ data: JSON.stringify(frame) }); }
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  FakeWebSocket.instances = [];
});

describe("WorkspaceRunSocket", () => {
  it("sends cancellation for the active run id", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const client = new WorkspaceRunSocket("client-a", () => undefined, () => undefined);
    client.connect();
    const socket = FakeWebSocket.instances[0];
    expect(socket.url).toContain("client_id=client-a");
    socket.open();
    client.cancel("run-9");

    expect(JSON.parse(socket.sent[0])).toEqual({ type: "cancel_run", run_id: "run-9" });
    client.close();
  });

  it("sends a scoped tool approval decision", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const client = new WorkspaceRunSocket("client-a", () => undefined, () => undefined);
    client.connect();
    const socket = FakeWebSocket.instances[0];
    socket.open();

    client.approve("run-1", "approval-1", true);

    expect(JSON.parse(socket.sent[0])).toEqual({
      type: "tool_approval",
      run_id: "run-1",
      approval_id: "approval-1",
      approved: true,
    });
    client.close();
  });
  it("reconnects and resumes the active run after its last durable event", () => {
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const frames: string[] = [];
    const client = new WorkspaceRunSocket(
      "client-a",
      (frame) => frames.push(frame.type),
      () => undefined,
    );

    client.connect();
    const first = FakeWebSocket.instances[0];
    first.open();
    client.sendMessage("session-1", "hello");
    first.emit({ type: "run_started", run_id: "run-1", sequence: 3, payload: {} });
    first.disconnect();
    vi.advanceTimersByTime(1_000);
    const second = FakeWebSocket.instances[1];
    second.open();

    expect(JSON.parse(first.sent[0])).toEqual({
      type: "send_message", session_id: "session-1", content: "hello",
    });
    expect(JSON.parse(second.sent[0])).toEqual({
      type: "resume_run", run_id: "run-1", after_sequence: 3, limit: 100,
    });
    expect(frames).toEqual(["run_started"]);
    client.close();
  });
});
