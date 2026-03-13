"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getAccessToken } from "@/lib/api";

const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`
    : "ws://localhost:8000");

export interface EngineEvent {
  event: string;
  timestamp: string;
  user_id: number | null;
  bot_name: string | null;
  data: Record<string, unknown>;
}

type EventHandler = (event: EngineEvent) => void;

/**
 * Manages a single WebSocket connection to the API server.
 * Reconnects automatically on disconnection.
 */
class WebSocketManager {
  private ws: WebSocket | null = null;
  private listeners = new Map<string, Set<EventHandler>>();
  private globalListeners = new Set<EventHandler>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;

  connect() {
    const token = getAccessToken();
    if (!token) return;

    const url = `${WS_BASE}/api/ws?token=${encodeURIComponent(token)}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
    };

    this.ws.onmessage = (msg) => {
      try {
        const event: EngineEvent = JSON.parse(msg.data);
        // Notify type-specific listeners
        const typeListeners = this.listeners.get(event.event);
        if (typeListeners) {
          typeListeners.forEach((fn) => fn(event));
        }
        // Notify global listeners
        this.globalListeners.forEach((fn) => fn(event));
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
      this.connect();
    }, this.reconnectDelay);
  }

  on(eventType: string, handler: EventHandler) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(handler);
  }

  off(eventType: string, handler: EventHandler) {
    this.listeners.get(eventType)?.delete(handler);
  }

  onAny(handler: EventHandler) {
    this.globalListeners.add(handler);
  }

  offAny(handler: EventHandler) {
    this.globalListeners.delete(handler);
  }
}

// Singleton instance
let manager: WebSocketManager | null = null;

function getManager(): WebSocketManager {
  if (!manager) {
    manager = new WebSocketManager();
  }
  return manager;
}

/**
 * Hook: Connect to WebSocket on mount, disconnect on unmount.
 * Returns the latest event of any type.
 */
export function useWebSocket(): { connected: boolean; lastEvent: EngineEvent | null } {
  const [lastEvent, setLastEvent] = useState<EngineEvent | null>(null);
  const [connected, setConnected] = useState(false);
  const mgr = useRef(getManager());

  useEffect(() => {
    const m = mgr.current;
    const handler: EventHandler = (event) => {
      setLastEvent(event);
      setConnected(true);
    };
    m.onAny(handler);
    m.connect();

    return () => {
      m.offAny(handler);
    };
  }, []);

  return { connected, lastEvent };
}

/**
 * Hook: Subscribe to a specific event type from the trading engine.
 */
export function useEngineEvent(eventType: string): EngineEvent | null {
  const [event, setEvent] = useState<EngineEvent | null>(null);
  const mgr = useRef(getManager());

  useEffect(() => {
    const m = mgr.current;
    const handler: EventHandler = (e) => setEvent(e);
    m.on(eventType, handler);
    m.connect();

    return () => {
      m.off(eventType, handler);
    };
  }, [eventType]);

  return event;
}

/**
 * Hook: Stream trade executions in real-time.
 */
export function useTradeStream(): EngineEvent | null {
  return useEngineEvent("trade_executed");
}

/**
 * Hook: Stream bot status changes in real-time.
 */
export function useBotStatus(): EngineEvent | null {
  return useEngineEvent("bot_status_changed");
}
