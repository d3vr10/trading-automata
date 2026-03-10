"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  getBotStatus, listPositions, listTrades, getPortfolioSummary, getEquityCurve,
  getAccountSnapshots, getPerBotPortfolioHistory, getDrawdownStats,
  type Trade, type Position, type PortfolioSummary, type EquityCurvePoint,
  type AccountsSummary, type PerBotHistoryPoint, type DrawdownStats,
} from "@/lib/api";
import { Link } from "@/i18n/navigation";
import { Sparkline } from "@/components/charts/sparkline";
import { MiniBarChart } from "@/components/charts/mini-bar-chart";
import { MultiLineSparkline, MultiLineSparklineLegend } from "@/components/charts/multi-line-sparkline";
import {
  Activity, TrendingUp, TrendingDown, BarChart3, ArrowUpRight, ArrowDownRight,
  DollarSign, PieChart,
} from "lucide-react";
import { CardSkeleton, ChartSkeleton, ListCardSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";
import { useTranslations } from "next-intl";
import { useWebSocket } from "@/hooks/use-websocket";

export default function DashboardPage() {
  const [bots, setBots] = useState<Record<string, any>>({});
  const [positions, setPositions] = useState<Position[]>([]);
  const [recentTrades, setRecentTrades] = useState<Trade[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [equityCurve, setEquityCurve] = useState<EquityCurvePoint[]>([]);
  const [accounts, setAccounts] = useState<AccountsSummary | null>(null);
  const [perBotHistory, setPerBotHistory] = useState<PerBotHistoryPoint[]>([]);
  const [drawdownStats, setDrawdownStats] = useState<DrawdownStats[]>([]);
  const [loading, setLoading] = useState(true);
  const t = useTranslations("dashboard");
  const { on } = useWebSocket();

  async function loadAll() {
    try {
      const [botData, posData, tradeData, portfolioData, curveData, accountData, historyData, ddData] = await Promise.all([
        getBotStatus().catch(() => ({})),
        listPositions(true).catch(() => []),
        listTrades({ limit: 10 }).catch(() => []),
        getPortfolioSummary().catch(() => null),
        getEquityCurve(90).catch(() => []),
        getAccountSnapshots().catch(() => null),
        getPerBotPortfolioHistory(90).catch(() => []),
        getDrawdownStats().catch(() => []),
      ]);
      setBots(botData);
      setPositions(posData);
      setRecentTrades(tradeData);
      setPortfolio(portfolioData);
      setEquityCurve(curveData);
      setAccounts(accountData);
      setPerBotHistory(historyData);
      setDrawdownStats(ddData);
    } finally {
      setLoading(false);
    }
  }

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const debouncedRefresh = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { loadAll(); }, 500);
  }, []);

  useEffect(() => { loadAll(); }, []);

  useEffect(() => {
    const unsubs = [
      on("bot_status_changed", debouncedRefresh),
      on("trade_executed", debouncedRefresh),
      on("account_snapshot", debouncedRefresh),
    ];
    return () => { unsubs.forEach((fn) => fn()); };
  }, [on, debouncedRefresh]);

  const botEntries = Object.entries(bots);
  const activeBots = botEntries.filter(([, s]: [string, any]) => s.running && !s.paused).length;

  const closedTrades = recentTrades.filter((tr) => tr.net_pnl !== null);
  const totalPnl = closedTrades.reduce((sum, tr) => sum + (tr.net_pnl || 0), 0);
  const winningCount = closedTrades.filter((tr) => tr.is_winning_trade).length;
  const winRate = closedTrades.length > 0 ? (winningCount / closedTrades.length) * 100 : 0;

  const hasLiveAccounts = accounts && accounts.total_equity > 0;
  const portfolioValue = hasLiveAccounts ? accounts.total_equity : (portfolio?.total_invested ?? 0);
  const availableCash = hasLiveAccounts ? accounts.total_cash : 0;

  // Build drawdown lookup
  const ddByBot = new Map(drawdownStats.map((d) => [d.bot_name, d]));

  // Build per-bot equity series for multi-line chart
  const botHistoryMap = new Map<string, { date: string; equity: number }[]>();
  for (const p of perBotHistory) {
    if (!botHistoryMap.has(p.bot_name)) botHistoryMap.set(p.bot_name, []);
    botHistoryMap.get(p.bot_name)!.push({ date: p.date, equity: p.equity });
  }
  const equitySeries = Array.from(botHistoryMap.entries()).map(([name, pts]) => ({
    label: name,
    data: pts.map((p) => p.equity),
  }));

  // Per-bot trades for win rate
  const tradesByBot = new Map<string, Trade[]>();
  for (const tr of recentTrades) {
    const key = tr.bot_name || "unknown";
    if (!tradesByBot.has(key)) tradesByBot.set(key, []);
    tradesByBot.get(key)!.push(tr);
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-7 w-32 bg-accent/60" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => <CardSkeleton key={i} />)}
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => <CardSkeleton key={i} />)}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <ListCardSkeleton rows={3} />
          <ListCardSkeleton rows={3} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>

      {/* Global summary row (compact) */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MiniSummary
          label={t("portfolioValue")}
          value={`$${portfolioValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          sub={hasLiveAccounts ? `$${availableCash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${t("availableCash")}` : undefined}
          icon={DollarSign}
        />
        <MiniSummary
          label={t("activeBots")}
          value={`${activeBots}/${botEntries.length}`}
          icon={Activity}
        />
        <MiniSummary
          label={t("realizedPnl")}
          value={`${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`}
          valueColor={totalPnl >= 0 ? "text-primary" : "text-destructive"}
          icon={TrendingUp}
        />
        <MiniSummary
          label={t("winRate")}
          value={`${winRate.toFixed(1)}%`}
          sub={t("tradesCount", { winning: winningCount, total: closedTrades.length })}
          icon={BarChart3}
        />
      </div>

      {/* Per-Account Cards (primary view) */}
      {hasLiveAccounts && accounts.accounts.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">{t("byAccount")}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {accounts.accounts.map((acc) => {
              const botName = acc.bot_name || "unknown";
              const status = bots[botName] as Record<string, any> | undefined;
              const isRunning = status?.running && !status?.paused;
              const isPaused = status?.paused;
              const dd = ddByBot.get(botName);
              const botTrades = tradesByBot.get(botName) || [];
              const closed = botTrades.filter((t) => t.net_pnl !== null);
              const botPnl = closed.reduce((s, t) => s + (t.net_pnl || 0), 0);
              const botWinning = closed.filter((t) => t.is_winning_trade).length;
              const botWinRate = closed.length > 0 ? (botWinning / closed.length) * 100 : 0;
              const botHistory = botHistoryMap.get(botName) || [];

              // Find bot config id from bots list for linking
              const botId = botEntries.find(([n]) => n === botName)?.[0];

              return (
                <Link
                  key={botName}
                  href={`/dashboard/bots/${encodeURIComponent(botName)}`}
                  className="glass rounded-2xl p-5 space-y-3 hover:bg-accent/10 transition-colors block"
                >
                  <div className="flex items-center justify-between">
                    <div className="min-w-0">
                      <h3 className="font-semibold truncate">{botName}</h3>
                      <span className="text-[11px] text-muted-foreground">{acc.broker_type} / {acc.currency}</span>
                    </div>
                    <Badge
                      variant={isPaused ? "secondary" : isRunning ? "default" : "destructive"}
                      className={isRunning ? "bg-primary/20 text-primary border-primary/30" : ""}
                    >
                      {isPaused ? t("statusPaused") : isRunning ? t("statusRunning") : t("statusStopped")}
                    </Badge>
                  </div>

                  <div className="text-2xl font-semibold">
                    ${acc.equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    ${acc.cash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {t("availableCash")}
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">{t("realizedPnl")}</span>
                      <div className={`font-medium ${botPnl >= 0 ? "text-primary" : "text-destructive"}`}>
                        {botPnl >= 0 ? "+" : ""}${botPnl.toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">{t("winRate")}</span>
                      <div className="font-medium">{botWinRate.toFixed(1)}%</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">{t("drawdown")}</span>
                      <div className={`font-medium ${(dd?.current_drawdown_pct || 0) > 5 ? "text-destructive" : "text-muted-foreground"}`}>
                        {dd ? `${dd.current_drawdown_pct.toFixed(1)}%` : "--"}
                      </div>
                    </div>
                  </div>

                  {botHistory.length >= 2 && (
                    <Sparkline
                      data={botHistory.map((p) => p.equity)}
                      width={300}
                      height={40}
                      className="w-full"
                      color="oklch(0.7 0.15 250)"
                      strokeWidth={1.2}
                    />
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Equity curves */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="glass rounded-2xl overflow-hidden lg:col-span-2">
          <div className="px-5 py-4 border-b border-border/30 flex items-center justify-between">
            <h2 className="font-semibold">{t("equityCurve")}</h2>
            {equityCurve.length > 0 && (
              <span className={`text-sm font-medium ${
                equityCurve[equityCurve.length - 1]?.cumulative_pnl >= 0 ? "text-primary" : "text-destructive"
              }`}>
                {equityCurve[equityCurve.length - 1]?.cumulative_pnl >= 0 ? "+" : ""}
                ${equityCurve[equityCurve.length - 1]?.cumulative_pnl.toFixed(2)}
              </span>
            )}
          </div>
          <div className="p-5">
            {equityCurve.length > 1 ? (
              <Sparkline
                data={equityCurve.map((p) => p.cumulative_pnl)}
                width={600}
                height={120}
                className="w-full"
              />
            ) : (
              <div className="text-muted-foreground text-sm text-center py-8">
                {t("equityCurveEmpty")}
              </div>
            )}
            {equityCurve.length > 1 && (
              <div className="mt-3">
                <MiniBarChart
                  data={equityCurve.slice(-30).map((p) => ({ label: p.date, value: p.daily_pnl }))}
                  width={600}
                  height={48}
                  className="w-full"
                />
                <p className="text-[11px] text-muted-foreground mt-1">{t("dailyPnl")}</p>
              </div>
            )}
          </div>
        </div>

        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border/30 flex items-center gap-2">
            <PieChart className="h-4 w-4 text-muted-foreground" />
            <h2 className="font-semibold">{t("allocation")}</h2>
          </div>
          <div className="p-5 space-y-5">
            {hasLiveAccounts && accounts.positions.length > 0 ? (
              <>
                <div className="space-y-2">
                  {accounts.positions.slice(0, 8).map((p) => (
                    <div key={`${p.bot_name}-${p.symbol}`} className="flex items-center justify-between text-sm">
                      <div className="min-w-0">
                        <span className="font-medium">{p.symbol}</span>
                        <span className="text-[10px] text-muted-foreground ml-1.5">{p.bot_name}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-muted-foreground">${p.market_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                        {p.unrealized_pnl !== 0 && (
                          <span className={`ml-2 text-xs ${p.unrealized_pnl >= 0 ? "text-primary" : "text-destructive"}`}>
                            {p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl.toFixed(2)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : portfolio && portfolio.allocations.length > 0 ? (
              <div className="space-y-2">
                {portfolio.allocations.slice(0, 6).map((a) => (
                  <div key={a.symbol} className="flex items-center justify-between text-sm">
                    <span className="font-medium">{a.symbol}</span>
                    <div className="text-right">
                      <span className="text-muted-foreground">${a.value.toFixed(2)}</span>
                      {a.unrealized_pnl !== 0 && (
                        <span className={`ml-2 text-xs ${a.unrealized_pnl >= 0 ? "text-primary" : "text-destructive"}`}>
                          {a.unrealized_pnl >= 0 ? "+" : ""}${a.unrealized_pnl.toFixed(2)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-muted-foreground text-sm text-center py-4">
                {t("noOpenPositions")}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Per-Account Equity Over Time (multi-line) */}
      {equitySeries.length > 0 && equitySeries.some((s) => s.data.length >= 2) && (
        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border/30 flex items-center justify-between">
            <h2 className="font-semibold">{t("perAccountEquity")}</h2>
          </div>
          <div className="p-5 space-y-3">
            <MultiLineSparkline series={equitySeries} width={800} height={100} className="w-full" />
            <MultiLineSparklineLegend series={equitySeries} />
          </div>
        </div>
      )}

      {/* Drawdown overview */}
      {drawdownStats.length > 0 && (
        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border/30 flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-muted-foreground" />
            <h2 className="font-semibold">{t("drawdownOverview")}</h2>
          </div>
          <div className="p-5">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {drawdownStats.map((dd) => (
                <div key={dd.bot_name} className="glass-subtle rounded-xl p-3 space-y-1">
                  <div className="font-medium text-sm">{dd.bot_name}</div>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">{t("currentDrawdown")}</span>
                    <span className={dd.current_drawdown_pct > 5 ? "text-destructive font-medium" : "text-muted-foreground"}>
                      {dd.current_drawdown_pct.toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">{t("maxDrawdown")}</span>
                    <span className="text-muted-foreground">{dd.max_drawdown_pct.toFixed(2)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border/30 flex items-center justify-between">
            <h2 className="font-semibold">{t("recentTrades")}</h2>
            <Link href="/dashboard/trades" className="text-xs text-primary hover:underline">{t("viewAll")}</Link>
          </div>
          <div className="p-5">
            {recentTrades.length === 0 ? (
              <p className="text-muted-foreground text-sm text-center py-4">{t("noTradesYet")}</p>
            ) : (
              <div className="space-y-2">
                {recentTrades.map((trade) => (
                  <div key={trade.id} className="flex items-center justify-between rounded-xl glass-subtle p-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{trade.symbol}</span>
                        {trade.is_winning_trade !== null && (
                          trade.is_winning_trade
                            ? <ArrowUpRight className="h-3.5 w-3.5 text-primary" />
                            : <ArrowDownRight className="h-3.5 w-3.5 text-destructive" />
                        )}
                      </div>
                      <span className="text-[11px] text-muted-foreground">{trade.bot_name} / {trade.strategy}</span>
                    </div>
                    <div className="text-right">
                      <span className={`font-medium ${
                        trade.net_pnl === null ? "text-muted-foreground" :
                        (trade.net_pnl || 0) >= 0 ? "text-primary" : "text-destructive"
                      }`}>
                        {trade.net_pnl !== null ? `$${trade.net_pnl.toFixed(2)}` : t("open")}
                      </span>
                      {trade.pnl_percent !== null && (
                        <span className="text-[11px] text-muted-foreground block">
                          {trade.pnl_percent >= 0 ? "+" : ""}{trade.pnl_percent.toFixed(2)}%
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border/30 flex items-center justify-between">
            <h2 className="font-semibold">{t("botStatus")}</h2>
            <Link href="/dashboard/bots" className="text-xs text-primary hover:underline">{t("viewAll")}</Link>
          </div>
          <div className="p-5">
            {botEntries.length === 0 ? (
              <p className="text-muted-foreground text-sm text-center py-4">{t("noBotsReporting")}</p>
            ) : (
              <div className="space-y-2">
                {botEntries.map(([name, status]: [string, any]) => (
                  <Link
                    key={name}
                    href={`/dashboard/bots/${encodeURIComponent(name)}`}
                    className="flex items-center justify-between rounded-xl glass-subtle p-3 hover:bg-accent/30 transition-colors"
                  >
                    <div className="min-w-0">
                      <span className="font-medium truncate block">{name}</span>
                      {status.strategy && (
                        <span className="text-[11px] text-muted-foreground">{status.strategy}</span>
                      )}
                    </div>
                    <Badge
                      variant={status.paused ? "secondary" : status.running ? "default" : "destructive"}
                      className={status.running && !status.paused ? "bg-primary/20 text-primary border-primary/30" : ""}
                    >
                      {status.paused ? t("statusPaused") : status.running ? t("statusRunning") : t("statusStopped")}
                    </Badge>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {portfolio && portfolio.recent_pnl.length > 1 && (
        <div className="glass rounded-2xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-sm">{t("recentTradePnl")}</h2>
            <span className="text-xs text-muted-foreground">{t("lastClosedTrades", { count: portfolio.recent_pnl.length })}</span>
          </div>
          <Sparkline
            data={portfolio.recent_pnl}
            width={800}
            height={60}
            className="w-full"
            color={portfolio.recent_pnl.reduce((a, b) => a + b, 0) >= 0 ? "oklch(0.75 0.18 160)" : "oklch(0.65 0.22 25)"}
          />
        </div>
      )}
    </div>
  );
}

function MiniSummary({
  label, value, valueColor, sub, icon: Icon,
}: {
  label: string;
  value: string;
  valueColor?: string;
  sub?: string;
  icon: typeof Activity;
}) {
  return (
    <div className="glass rounded-xl px-4 py-3 flex items-center gap-3">
      <div className="h-8 w-8 rounded-lg bg-accent/30 flex items-center justify-center shrink-0">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="min-w-0">
        <div className="text-[11px] text-muted-foreground">{label}</div>
        <div className={`text-lg font-semibold leading-tight ${valueColor || ""}`}>{value}</div>
        {sub && <div className="text-[10px] text-muted-foreground">{sub}</div>}
      </div>
    </div>
  );
}
