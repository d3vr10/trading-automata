"use client";

import { useEffect, useState } from "react";
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
  listTrades, listBots, type Trade, type BotConfig,
} from "@/lib/api";
import { useBotStatus } from "@/lib/websocket";
import { toast } from "sonner";
import { ArrowLeft, Play, Pause, Square } from "lucide-react";
import { StatusCardSkeleton, TableSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

export default function BotDetailPage() {
  const t = useTranslations("bots");
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const botId = Number(params.id);

  const [bot, setBot] = useState<BotConfig | null>(null);
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  const statusEvent = useBotStatus();

  async function load() {
    try {
      const [allBots, allStatus] = await Promise.all([
        listBots().catch(() => []),
        getBotStatus().catch(() => ({}) as Record<string, unknown>),
      ]);
      const found = allBots.find((b) => b.id === botId) ?? null;
      setBot(found);
      if (found) {
        setStatus((allStatus[found.name] as Record<string, unknown>) ?? null);
        const botTrades = await listTrades({ bot_name: found.name, limit: 20 }).catch(() => []);
        setTrades(botTrades);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [botId]);

  useEffect(() => {
    if (bot && statusEvent?.bot_name === bot.name) load();
  }, [statusEvent]);

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
