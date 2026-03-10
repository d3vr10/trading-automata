"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  getBotStatus, startBot, pauseBot, resumeBot, stopBot,
  listTrades, listBots, getBotEvents, getBotStats,
  type Trade, type BotConfig, type BotEvent, type BotStats,
} from "@/lib/api";
import { Sparkline } from "@/components/charts/sparkline";
import { toast } from "sonner";
import {
  ArrowLeft, Play, Pause, Square, RefreshCw, Target, BarChart3,
  TrendingUp, TrendingDown, Zap, AlertTriangle, RotateCw, Radio,
} from "lucide-react";
import { StatusCardSkeleton, TableSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";
import { useWebSocket, type WsEvent } from "@/hooks/use-websocket";

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

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export default function BotDetailPage() {
  const t = useTranslations("bots");
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const botId = Number(params.id);

  const [bot, setBot] = useState<BotConfig | null>(null);
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [events, setEvents] = useState<BotEvent[]>([]);
  const [stats, setStats] = useState<BotStats | null>(null);
  const [loading, setLoading] = useState(true);
  const { isConnected, on } = useWebSocket();

  const load = useCallback(async () => {
    try {
      const [allBots, allStatus] = await Promise.all([
        listBots().catch(() => []),
        getBotStatus().catch(() => ({}) as Record<string, unknown>),
      ]);
      const found = allBots.find((b) => b.id === botId) ?? null;
      setBot(found);
      if (found) {
        setStatus((allStatus[found.name] as Record<string, unknown>) ?? null);
        const [botTrades, botEvents, botStats] = await Promise.all([
          listTrades({ bot_name: found.name, limit: 20 }).catch(() => []),
          getBotEvents(botId, 50).catch(() => []),
          getBotStats(botId).catch(() => null),
        ]);
        setTrades(botTrades);
        setEvents(botEvents);
        setStats(botStats);
      }
    } finally {
      setLoading(false);
    }
  }, [botId]);

  useEffect(() => { load(); }, [load]);

  // Real-time updates via WebSocket
  useEffect(() => {
    if (!bot) return;
    const cleanups = [
      on("*", (ws: WsEvent) => {
        if (ws.bot_name !== bot.name) return;
        // Prepend to activity feed
        const newEvent: BotEvent = {
          type: ws.event as BotEvent["type"],
          timestamp: ws.timestamp,
          data: ws.data as Record<string, any>,
        };
        setEvents((prev) => [newEvent, ...prev].slice(0, 50));
      }),
      on("bot_status_changed", (ws: WsEvent) => {
        if (ws.bot_name !== bot.name) return;
        // Refresh full status from API
        getBotStatus().then((all) => {
          setStatus((all[bot.name] as Record<string, unknown>) ?? null);
        }).catch(() => {});
      }),
      on("trade_executed", (ws: WsEvent) => {
        if (ws.bot_name !== bot.name) return;
        // Refresh trades list
        listTrades({ bot_name: bot.name, limit: 20 }).then(setTrades).catch(() => {});
      }),
    ];
    return () => cleanups.forEach((fn) => fn());
  }, [bot, on]);

  async function handleAction(action: "start" | "pause" | "resume" | "stop") {
    try {
      if (action === "start") await startBot(botId);
      else if (action === "pause") await pauseBot(botId);
      else if (action === "resume") await resumeBot(botId);
      else await stopBot(botId);
      toast.success(t("actionSent", { botName: bot?.name ?? "", action }));
      setTimeout(load, 1000);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("actionFailed", { action }));
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-9 w-9 rounded-xl bg-accent/50" />
          <Skeleton className="h-7 w-40 bg-accent/60" />
          <Skeleton className="h-5 w-16 rounded-full bg-accent/50" />
        </div>
        <StatusCardSkeleton />
        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border/30">
            <Skeleton className="h-5 w-32 bg-accent/60" />
          </div>
          <table className="w-full">
            <tbody>
              <TableSkeleton columns={6} rows={4} />
            </tbody>
          </table>
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
        <div className="glass rounded-2xl p-8 text-center text-muted-foreground">
          {t("detail.notFoundDescription")}
        </div>
      </div>
    );
  }

  const isRunning = (status as any)?.running === true;
  const isPaused = (status as any)?.paused === true;
  const isStopped = !isRunning;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" className="rounded-xl" onClick={() => router.push("/dashboard/bots")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">{bot.name}</h1>
        <Badge
          variant={isPaused ? "secondary" : isRunning ? "default" : "destructive"}
          className={isRunning && !isPaused ? "bg-primary/20 text-primary border-primary/30" : ""}
        >
          {isPaused ? t("statusPaused") : isRunning ? t("statusRunning") : t("statusStopped")}
        </Badge>
      </div>

      {/* Config + Status */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border/30">
          <h2 className="font-semibold">{t("detail.configuration")}</h2>
        </div>
        <div className="p-5 space-y-5">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="glass-subtle rounded-xl p-3">
              <div className="text-xs text-muted-foreground">{t("strategy")}</div>
              <div className="font-medium mt-1">{bot.strategy_id}</div>
            </div>
            <div className="glass-subtle rounded-xl p-3">
              <div className="text-xs text-muted-foreground">{t("broker")}</div>
              <div className="font-medium mt-1">{bot.broker_type} / {bot.environment}</div>
            </div>
            <div className="glass-subtle rounded-xl p-3">
              <div className="text-xs text-muted-foreground">{t("allocation")}</div>
              <div className="font-medium mt-1">${bot.allocation.toFixed(2)}</div>
            </div>
            <div className="glass-subtle rounded-xl p-3">
              <div className="text-xs text-muted-foreground">{t("virtualBalance")}</div>
              <div className="font-medium mt-1">${(status as any)?.virtual_balance?.toFixed(2) ?? "—"}</div>
            </div>
            <div className="glass-subtle rounded-xl p-3">
              <div className="text-xs text-muted-foreground">{t("fenceType")}</div>
              <div className="font-medium mt-1">{bot.fence_type}</div>
            </div>
            <div className="glass-subtle rounded-xl p-3">
              <div className="text-xs text-muted-foreground">{t("detail.stopLoss")}</div>
              <div className="font-medium mt-1">{bot.stop_loss_pct}%</div>
            </div>
            <div className="glass-subtle rounded-xl p-3">
              <div className="text-xs text-muted-foreground">{t("detail.takeProfit")}</div>
              <div className="font-medium mt-1">{bot.take_profit_pct}%</div>
            </div>
            <div className="glass-subtle rounded-xl p-3">
              <div className="text-xs text-muted-foreground">{t("detail.maxPositionSize")}</div>
              <div className="font-medium mt-1">{(bot.max_position_size * 100).toFixed(0)}%</div>
            </div>
          </div>

          <div className="flex gap-2">
            {isStopped && (
              <Button size="sm" className="rounded-lg" onClick={() => handleAction("start")}>
                <Play className="mr-1 h-3.5 w-3.5" /> {t("start")}
              </Button>
            )}
            {isRunning && !isPaused && (
              <Button size="sm" variant="secondary" className="rounded-lg" onClick={() => handleAction("pause")}>
                <Pause className="mr-1 h-3.5 w-3.5" /> {t("pause")}
              </Button>
            )}
            {isPaused && (
              <Button size="sm" className="rounded-lg" onClick={() => handleAction("resume")}>
                <Play className="mr-1 h-3.5 w-3.5" /> {t("resume")}
              </Button>
            )}
            {isRunning && (
              <Button size="sm" variant="destructive" className="rounded-lg" onClick={() => handleAction("stop")}>
                <Square className="mr-1 h-3.5 w-3.5" /> {t("stop")}
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Performance Stats */}
      {stats && stats.total_trades > 0 && (
        <>
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
            <div className="glass rounded-2xl p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <TrendingUp className="h-3.5 w-3.5" />
                {t("detail.totalPnl")}
              </div>
              <div className={`text-xl font-semibold mt-1 ${stats.total_pnl >= 0 ? "text-primary" : "text-destructive"}`}>
                {stats.total_pnl >= 0 ? "+" : ""}${stats.total_pnl.toFixed(2)}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                avg {stats.avg_pnl_percent >= 0 ? "+" : ""}{stats.avg_pnl_percent}%
              </div>
            </div>
            <div className="glass rounded-2xl p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Target className="h-3.5 w-3.5" />
                {t("detail.winRate")}
              </div>
              <div className="text-xl font-semibold mt-1">{stats.win_rate}%</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {stats.winning_trades}/{stats.total_trades} {t("detail.tradeCount").toLowerCase()}
              </div>
            </div>
            <div className="glass rounded-2xl p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <BarChart3 className="h-3.5 w-3.5" />
                {t("detail.tradeCount")}
              </div>
              <div className="text-xl font-semibold mt-1">{stats.total_trades}</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                <span className="text-primary">{t("detail.bestTrade")}: +${stats.best_trade.toFixed(2)}</span>
              </div>
            </div>
            <div className="glass rounded-2xl p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <TrendingDown className="h-3.5 w-3.5" />
                {t("detail.equity")}
              </div>
              <div className="text-xl font-semibold mt-1">
                {stats.equity != null ? `$${stats.equity.toFixed(2)}` : "—"}
              </div>
              {stats.cash != null && (
                <div className="text-xs text-muted-foreground mt-0.5">
                  ${stats.cash.toFixed(2)} cash
                </div>
              )}
            </div>
          </div>

          {/* Mini Equity Curve */}
          {stats.equity_curve.length >= 2 && (
            <div className="glass rounded-2xl overflow-hidden">
              <div className="px-5 py-4 border-b border-border/30">
                <h2 className="font-semibold">{t("detail.equityCurve")}</h2>
              </div>
              <div className="p-5">
                <Sparkline
                  data={stats.equity_curve.map((p) => p.cumulative_pnl)}
                  width={800}
                  height={80}
                  color={stats.total_pnl >= 0 ? "oklch(0.75 0.18 160)" : "oklch(0.65 0.2 25)"}
                  className="w-full"
                />
              </div>
            </div>
          )}
        </>
      )}

      {/* Live Activity Feed */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border/30">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold">{t("detail.activityFeed")}</h2>
            {isConnected && (
              <span className="flex items-center gap-1 text-xs text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live
              </span>
            )}
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="rounded-lg h-7 w-7 p-0"
            onClick={load}
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {events.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">
              {t("detail.noActivity")}
            </div>
          ) : (
            <div className="divide-y divide-border/20">
              {events.map((event, i) => {
                const Icon = EVENT_ICONS[event.type] ?? Zap;
                const color = EVENT_COLORS[event.type] ?? "text-muted-foreground";
                return (
                  <div key={`${event.timestamp}-${i}`} className="flex items-start gap-3 px-5 py-3 hover:bg-accent/10 transition-colors">
                    <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${color}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm">{formatEvent(event)}</p>
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0">{timeAgo(event.timestamp)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Recent Trades */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border/30">
          <h2 className="font-semibold">{t("detail.recentActivity")}</h2>
        </div>
        {trades.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground text-sm">
            {t("detail.noActivity")}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-border/30 hover:bg-transparent">
                <TableHead className="text-muted-foreground/80">{t("detail.symbol")}</TableHead>
                <TableHead className="text-muted-foreground/80">{t("strategy")}</TableHead>
                <TableHead className="text-right text-muted-foreground/80">{t("detail.entry")}</TableHead>
                <TableHead className="text-right text-muted-foreground/80">{t("detail.exit")}</TableHead>
                <TableHead className="text-right text-muted-foreground/80">{t("detail.pnl")}</TableHead>
                <TableHead className="text-right text-muted-foreground/80">{t("detail.pnlPercent")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {trades.map((trade) => (
                <TableRow key={trade.id} className="border-border/20 hover:bg-accent/20">
                  <TableCell className="font-medium">{trade.symbol}</TableCell>
                  <TableCell className="text-muted-foreground">{trade.strategy}</TableCell>
                  <TableCell className="text-right">${trade.entry_price.toFixed(2)}</TableCell>
                  <TableCell className="text-right">
                    {trade.exit_price != null ? `$${trade.exit_price.toFixed(2)}` : t("detail.open")}
                  </TableCell>
                  <TableCell className={`text-right font-medium ${(trade.net_pnl ?? 0) >= 0 ? "text-primary" : "text-destructive"}`}>
                    {trade.net_pnl != null ? `$${trade.net_pnl.toFixed(2)}` : "--"}
                  </TableCell>
                  <TableCell className={`text-right ${(trade.pnl_percent ?? 0) >= 0 ? "text-primary" : "text-destructive"}`}>
                    {trade.pnl_percent != null ? `${trade.pnl_percent.toFixed(1)}%` : "--"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
