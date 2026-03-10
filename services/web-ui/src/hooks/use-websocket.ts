"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getWebSocketUrl } from "@/lib/api";

export interface WsEvent {
  event: string;
  timestamp: string;
  user_id: number | null;
  bot_name: string | null;
  data: Record<string, unknown>;
}

type EventHandler = (event: WsEvent) => void;

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const handlersRef = useRef<Map<string, Set<EventHandler>>>(new Map());
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retriesRef = useRef(0);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    try {
      const url = getWebSocketUrl();
      if (!url || url.includes("null")) return; // no token yet

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        retriesRef.current = 0;
      };

      ws.onmessage = (msg) => {
        try {
          const event: WsEvent = JSON.parse(msg.data);
          const eventType = event.event;

          // Fire type-specific handlers
          const handlers = handlersRef.current.get(eventType);
          if (handlers) {
            handlers.forEach((fn) => fn(event));
          }
          // Fire wildcard handlers
          const wildcards = handlersRef.current.get("*");
          if (wildcards) {
            wildcards.forEach((fn) => fn(event));
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        if (mountedRef.current) {
          const delay = Math.min(1000 * 2 ** retriesRef.current, 30000);
          retriesRef.current++;
          reconnectTimer.current = setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // connection failed, will retry via onclose
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const on = useCallback((eventType: string, handler: EventHandler) => {
    if (!handlersRef.current.has(eventType)) {
      handlersRef.current.set(eventType, new Set());
    }
    handlersRef.current.get(eventType)!.add(handler);

    // Return cleanup function
    return () => {
      handlersRef.current.get(eventType)?.delete(handler);
    };
  }, []);

  return { isConnected, on };
}
