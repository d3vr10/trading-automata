"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getBotEvents, listBots,
  type BotConfig, type BotEvent,
} from "@/lib/api";
import {
  ArrowLeft, RefreshCw, Zap, TrendingUp, RotateCw,
  AlertTriangle, Radio, Filter,
} from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useWebSocket, type WsEvent } from "@/hooks/use-websocket";

const EVENT_TYPES = [
  "signal_generated",
  "trade_executed",
  "cycle_complete",
  "error",
  "bot_status_changed",
] as const;

const EVENT_ICONS: Record<string, typeof Zap> = {
  signal_generated: Zap,
  trade_executed: TrendingUp,
  cycle_complete: RotateCw,
  error: AlertTriangle,
  bot_status_changed: Radio,
};

const EVENT_COLORS: Record<string, string> = {
  signal_generated: "text-blue-400",
  trade_executed: "text-emerald-400",
  cycle_complete: "text-muted-foreground",
  error: "text-red-400",
  bot_status_changed: "text-amber-400",
};

const EVENT_BG: Record<string, string> = {
  signal_generated: "bg-blue-500/10 border-blue-500/30 text-blue-400",
  trade_executed: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
  cycle_complete: "bg-muted/50 border-border/30 text-muted-foreground",
  error: "bg-red-500/10 border-red-500/30 text-red-400",
  bot_status_changed: "bg-amber-500/10 border-amber-500/30 text-amber-400",
};

function formatEvent(event: BotEvent): string {
  const d = event.data;
  switch (event.type) {
    case "signal_generated": {
      const action = d.action?.toUpperCase() ?? "SIGNAL";
      const conf = d.confidence ? ` (${(d.confidence * 100).toFixed(0)}%)` : "";
      return `${action} signal on ${d.symbol ?? "?"} at $${Number(d.price ?? 0).toFixed(2)} — ${d.strategy ?? ""}${conf}`;
    }
    case "trade_executed":
      return `${d.action?.toUpperCase() ?? "TRADE"} ${d.symbol ?? "?"} x${d.quantity ?? "?"} at $${Number(d.price ?? 0).toFixed(2)} — ${d.strategy ?? ""}`;
    case "cycle_complete":
      return `Cycle #${d.cycle ?? "?"} — ${d.symbols_scanned ?? 0} symbols, ${d.pending_orders ?? 0} pending orders`;
    case "error":
      return d.message ?? "Unknown error";
    case "bot_status_changed":
      return `Status → ${d.status ?? "?"}`;
    default:
      return JSON.stringify(d);
  }
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export default function BotActivityLogPage() {
  const t = useTranslations("bots");
  const tLog = useTranslations("bots.log");
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const botId = Number(params.id);

  const [bot, setBot] = useState<BotConfig | null>(null);
  const [events, setEvents] = useState<BotEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set());
  const { isConnected, on } = useWebSocket();

  const load = useCallback(async () => {
    try {
      const allBots = await listBots().catch(() => []);
      const found = allBots.find((b) => b.id === botId) ?? null;
      setBot(found);
      if (found) {
        const botEvents = await getBotEvents(botId, 200).catch(() => []);
        setEvents(botEvents);
      }
    } finally {
      setLoading(false);
    }
  }, [botId]);

  useEffect(() => { load(); }, [load]);

  // Real-time updates
  useEffect(() => {
    if (!bot) return;
    return on("*", (ws: WsEvent) => {
      if (ws.bot_name !== bot.name) return;
      const newEvent: BotEvent = {
        type: ws.event as BotEvent["type"],
        timestamp: ws.timestamp,
        data: ws.data as Record<string, any>,
      };
      setEvents((prev) => [newEvent, ...prev].slice(0, 200));
    });
  }, [bot, on]);

  function toggleFilter(type: string) {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  const filtered = activeFilters.size === 0
    ? events
    : events.filter((e) => activeFilters.has(e.type));

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-7 w-60 bg-accent/60" />
        <Skeleton className="h-10 w-full bg-accent/40" />
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full bg-accent/30" />
          ))}
        </div>
      </div>
    );
  }

  if (!bot) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" className="rounded-xl" onClick={() => router.push("/dashboard/bots")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-2xl font-semibold tracking-tight">{t("detail.notFound")}</h1>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" className="rounded-xl" onClick={() => router.push(`/dashboard/bots/${botId}`)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{bot.name}</h1>
          <p className="text-sm text-muted-foreground">{tLog("title")}</p>
        </div>
        {isConnected && (
          <span className="flex items-center gap-1 text-xs text-emerald-400 ml-auto">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Live
          </span>
        )}
        <Button size="sm" variant="ghost" className="rounded-lg" onClick={load}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        {EVENT_TYPES.map((type) => {
          const active = activeFilters.has(type);
          const Icon = EVENT_ICONS[type];
          return (
            <button
              key={type}
              onClick={() => toggleFilter(type)}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition-colors ${
                active ? EVENT_BG[type] : "border-border/30 text-muted-foreground hover:bg-accent/20"
              }`}
            >
              <Icon className="h-3 w-3" />
              {tLog(type)}
            </button>
          );
        })}
        {activeFilters.size > 0 && (
          <button
            onClick={() => setActiveFilters(new Set())}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors ml-1"
          >
            {tLog("clearFilters")}
          </button>
        )}
      </div>

      {/* Event count */}
      <p className="text-xs text-muted-foreground">
        {tLog("showing", { count: filtered.length, total: events.length })}
      </p>

      {/* Events list */}
      <div className="glass rounded-2xl overflow-hidden">
        {filtered.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground text-sm">
            {activeFilters.size > 0 ? tLog("noMatchingEvents") : t("detail.noActivity")}
          </div>
        ) : (
          <div className="divide-y divide-border/20">
            {filtered.map((event, i) => {
              const Icon = EVENT_ICONS[event.type] ?? Zap;
              const color = EVENT_COLORS[event.type] ?? "text-muted-foreground";
              return (
                <div key={`${event.timestamp}-${i}`} className="flex items-start gap-3 px-5 py-3 hover:bg-accent/10 transition-colors">
                  <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${color}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">{formatEvent(event)}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Badge variant="outline" className={`text-[9px] px-1.5 py-0 ${EVENT_BG[event.type] ?? ""}`}>
                        {tLog(event.type)}
                      </Badge>
                      <span className="text-[10px] text-muted-foreground">{formatTimestamp(event.timestamp)}</span>
                    </div>
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">{timeAgo(event.timestamp)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
