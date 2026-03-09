import type { LiveEvent } from "../types/alerts";

const WS_URL = import.meta.env?.VITE_WS_URL ?? "ws://localhost:8000/ws/live";

export function connectLiveSocket(onEvent: (event: LiveEvent) => void, onStatus?: (status: string) => void): () => void {
  const socket = new WebSocket(WS_URL);
  let heartbeat: number | undefined;

  socket.onopen = () => {
    onStatus?.("connected");
    socket.send(JSON.stringify({ type: "hello" }));
    heartbeat = window.setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "ping" }));
      }
    }, 25000);
  };

  socket.onmessage = (event) => {
    onEvent(JSON.parse(event.data) as LiveEvent);
  };

  socket.onclose = () => {
    onStatus?.("closed");
    if (heartbeat) {
      window.clearInterval(heartbeat);
    }
  };

  socket.onerror = () => onStatus?.("error");

  return () => {
    if (heartbeat) {
      window.clearInterval(heartbeat);
    }
    socket.close();
  };
}
