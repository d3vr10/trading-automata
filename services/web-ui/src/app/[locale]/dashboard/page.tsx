"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  getBotStatus, listPositions, listTrades, getPortfolioSummary, getEquityCurve,
  type Trade, type Position, type PortfolioSummary, type EquityCurvePoint,
} from "@/lib/api";
import { Link } from "@/i18n/navigation";
import { Sparkline } from "@/components/charts/sparkline";
import { MiniBarChart } from "@/components/charts/mini-bar-chart";
import { AllocationBar } from "@/components/charts/allocation-bar";
import {
  Activity, TrendingUp, BarChart3, ArrowUpRight, ArrowDownRight,
  DollarSign, PieChart,
} from "lucide-react";
import { CardSkeleton, ChartSkeleton, ListCardSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";
import { useTranslations } from "next-intl";

export default function DashboardPage() {
  const [bots, setBots] = useState<Record<string, any>>({});
  const [positions, setPositions] = useState<Position[]>([]);
  const [recentTrades, setRecentTrades] = useState<Trade[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [equityCurve, setEquityCurve] = useState<EquityCurvePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const t = useTranslations("dashboard");

  useEffect(() => {
    async function load() {
      try {
        const [botData, posData, tradeData, portfolioData, curveData] = await Promise.all([
          getBotStatus().catch(() => ({})),
          listPositions(true).catch(() => []),
          listTrades({ limit: 10 }).catch(() => []),
          getPortfolioSummary().catch(() => null),
          getEquityCurve(90).catch(() => []),
        ]);
        setBots(botData);
        setPositions(posData);
        setRecentTrades(tradeData);
        setPortfolio(portfolioData);
        setEquityCurve(curveData);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const botEntries = Object.entries(bots);
  const activeBots = botEntries.filter(([, s]: [string, any]) => s.running && !s.paused).length;

  const closedTrades = recentTrades.filter((tr) => tr.net_pnl !== null);
  const totalPnl = closedTrades.reduce((sum, tr) => sum + (tr.net_pnl || 0), 0);
  const winningCount = closedTrades.filter((tr) => tr.is_winning_trade).length;
  const winRate = closedTrades.length > 0 ? (winningCount / closedTrades.length) * 100 : 0;

  const unrealizedPnl = portfolio?.total_unrealized_pnl ?? 0;
  const totalInvested = portfolio?.total_invested ?? 0;

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-7 w-32 bg-accent/60" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => <CardSkeleton key={i} />)}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2"><ChartSkeleton height={120} /></div>
          <ChartSkeleton height={180} />
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

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label={t("portfolioValue")}
          icon={DollarSign}
          iconBg="bg-primary/10"
          iconColor="text-primary"
          value={`$${totalInvested.toFixed(2)}`}
          sub={
            unrealizedPnl !== 0
              ? { value: `${unrealizedPnl >= 0 ? "+" : ""}$${unrealizedPnl.toFixed(2)}`, positive: unrealizedPnl >= 0 }
              : undefined
          }
        />
        <SummaryCard
          label={t("activeBots")}
          icon={Activity}
          iconBg="bg-chart-5/10"
          iconColor="text-chart-5"
          value={String(activeBots)}
          sub={{ value: t("totalLabel", { count: botEntries.length }), positive: true }}
        />
        <SummaryCard
          label={t("realizedPnl")}
          icon={TrendingUp}
          iconBg="bg-chart-3/10"
          iconColor="text-chart-3"
          value={`${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`}
          valueColor={totalPnl >= 0 ? "text-primary" : "text-destructive"}
        />
        <SummaryCard
          label={t("winRate")}
          icon={BarChart3}
          iconBg="bg-chart-4/10"
          iconColor="text-chart-4"
          value={`${winRate.toFixed(1)}%`}
          sub={{ value: t("tradesCount", { winning: winningCount, total: closedTrades.length }), positive: winRate >= 50 }}
        />
      </div>

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
            {portfolio && portfolio.allocations.length > 0 ? (
              <>
                <AllocationBar
                  items={portfolio.allocations.map((a) => ({ label: a.symbol, value: a.value }))}
                />
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
                {portfolio.by_strategy.length > 0 && (
                  <div className="pt-3 border-t border-border/20 space-y-1.5">
                    <p className="text-xs text-muted-foreground font-medium">{t("byStrategy")}</p>
                    {portfolio.by_strategy.map((s) => (
                      <div key={s.strategy} className="flex justify-between text-xs text-muted-foreground">
                        <span>{s.strategy}</span>
                        <span>{s.positions} pos &middot; ${s.value.toFixed(0)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="text-muted-foreground text-sm text-center py-4">
                {t("noOpenPositions")}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
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
                      <span className="text-[11px] text-muted-foreground">{trade.strategy}</span>
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

function SummaryCard({
  label, icon: Icon, iconBg, iconColor, value, valueColor, sub,
}: {
  label: string;
  icon: typeof Activity;
  iconBg: string;
  iconColor: string;
  value: string;
  valueColor?: string;
  sub?: { value: string; positive: boolean };
}) {
  return (
    <div className="glass rounded-2xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <div className={`h-8 w-8 rounded-xl ${iconBg} flex items-center justify-center`}>
          <Icon className={`h-4 w-4 ${iconColor}`} />
        </div>
      </div>
      <div className={`text-3xl font-semibold ${valueColor || ""}`}>{value}</div>
      {sub && (
        <p className="text-xs text-muted-foreground">
          <span className={sub.positive ? "text-primary" : "text-destructive"}>{sub.value}</span>
        </p>
      )}
    </div>
  );
}
