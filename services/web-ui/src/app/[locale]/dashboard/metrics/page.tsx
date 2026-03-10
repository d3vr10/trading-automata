"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CardSkeleton, ChartSkeleton } from "@/components/skeletons";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { getAnalytics, type Analytics } from "@/lib/api";
import { Sparkline } from "@/components/charts/sparkline";
import { MiniBarChart } from "@/components/charts/mini-bar-chart";
import { ProgressRing } from "@/components/charts/progress-ring";
import {
  BarChart3, Trophy,
} from "lucide-react";

export default function MetricsPage() {
  const t = useTranslations("metrics");
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    setLoading(true);
    getAnalytics({
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    })
      .then(setAnalytics)
      .catch(() => setAnalytics(null))
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  function handleDateChange(type: "from" | "to", value: string) {
    if (type === "from") setDateFrom(value);
    else setDateTo(value);
  }

  const dateFilters = (
    <div className="flex flex-wrap gap-3 items-center">
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground">{t("filters.dateFrom")}</label>
        <Input type="date" value={dateFrom} onChange={(e) => handleDateChange("from", e.target.value)} className="h-8 w-auto rounded-lg text-sm" />
      </div>
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground">{t("filters.dateTo")}</label>
        <Input type="date" value={dateTo} onChange={(e) => handleDateChange("to", e.target.value)} className="h-8 w-auto rounded-lg text-sm" />
      </div>
      {(dateFrom || dateTo) && (
        <Button variant="ghost" size="sm" className="rounded-lg h-8 text-xs" onClick={() => { setDateFrom(""); setDateTo(""); }}>
          {t("filters.clear")}
        </Button>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        {dateFilters}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => <CardSkeleton key={i} />)}
        </div>
        <ChartSkeleton height={160} />
      </div>
    );
  }

  if (!analytics || analytics.summary.total_trades === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        {dateFilters}
        <div className="glass rounded-2xl p-12 text-center space-y-4">
          <div className="h-14 w-14 rounded-2xl bg-chart-4/10 flex items-center justify-center mx-auto">
            <BarChart3 className="h-7 w-7 text-chart-4" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">{t("overview.noData")}</h2>
          </div>
        </div>
      </div>
    );
  }

  const { summary, by_strategy, by_symbol, equity_curve } = analytics;
  const bestStrategy = by_strategy.reduce((best, s) => s.win_rate > (best?.win_rate ?? 0) ? s : best, by_strategy[0]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>

      {dateFilters}

      {/* Overview stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="glass rounded-2xl p-5 space-y-2">
          <span className="text-sm text-muted-foreground">{t("overview.totalTrades")}</span>
          <div className="text-3xl font-semibold">{summary.total_trades}</div>
          <p className="text-xs text-muted-foreground">
            <span className="text-primary">{summary.winning_trades}W</span>
            {" / "}
            <span className="text-destructive">{summary.total_trades - summary.winning_trades}L</span>
          </p>
        </div>
        <div className="glass rounded-2xl p-5 space-y-2">
          <span className="text-sm text-muted-foreground">{t("overview.winRate")}</span>
          <div className="flex items-center gap-3">
            <ProgressRing value={summary.win_rate} size={56} strokeWidth={4}>
              <span className="text-xs font-bold">{summary.win_rate.toFixed(1)}%</span>
            </ProgressRing>
          </div>
        </div>
        <div className="glass rounded-2xl p-5 space-y-2">
          <span className="text-sm text-muted-foreground">{t("overview.totalPnl")}</span>
          <div className={`text-3xl font-semibold ${summary.total_pnl >= 0 ? "text-primary" : "text-destructive"}`}>
            {summary.total_pnl >= 0 ? "+" : ""}${summary.total_pnl.toFixed(2)}
          </div>
        </div>
        <div className="glass rounded-2xl p-5 space-y-2">
          <span className="text-sm text-muted-foreground">{t("strategiesTable.best")}</span>
          <div className="font-semibold">{bestStrategy?.strategy || "-"}</div>
          {bestStrategy && (
            <p className="text-xs text-primary">{bestStrategy.win_rate.toFixed(1)}% {t("winRateSuffix")}</p>
          )}
        </div>
      </div>

      {/* Equity curve */}
      {equity_curve.length > 1 && (
        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border/30 flex items-center justify-between">
            <h2 className="font-semibold">{t("equityCurve")}</h2>
            <span className={`text-sm font-medium ${
              equity_curve[equity_curve.length - 1].cumulative_pnl >= 0 ? "text-primary" : "text-destructive"
            }`}>
              {equity_curve[equity_curve.length - 1].cumulative_pnl >= 0 ? "+" : ""}
              ${equity_curve[equity_curve.length - 1].cumulative_pnl.toFixed(2)}
            </span>
          </div>
          <div className="p-5">
            <Sparkline
              data={equity_curve.map((p) => p.cumulative_pnl)}
              width={800}
              height={160}
              className="w-full"
              strokeWidth={2}
            />
            <div className="mt-4">
              <MiniBarChart
                data={equity_curve.map((p) => ({ label: p.date, value: p.daily_pnl }))}
                width={800}
                height={56}
                className="w-full"
              />
              <p className="text-[11px] text-muted-foreground mt-1">{t("dailyPnl")}</p>
            </div>
          </div>
        </div>
      )}

      {/* Strategy breakdown */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border/30">
          <h2 className="font-semibold">{t("tabs.strategies")}</h2>
        </div>
        <Table>
          <TableHeader>
            <TableRow className="border-border/30 hover:bg-transparent">
              <TableHead className="text-muted-foreground/80">{t("strategiesTable.strategy")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("strategiesTable.trades")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("strategiesTable.winRate")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("strategiesTable.avgPnl")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("strategiesTable.totalPnl")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("strategiesTable.best")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("strategiesTable.worst")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {by_strategy.map((s) => (
              <TableRow key={s.strategy} className="border-border/20 hover:bg-accent/20">
                <TableCell>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{s.strategy}</span>
                    {s.strategy === bestStrategy?.strategy && (
                      <Trophy className="h-3.5 w-3.5 text-chart-3" />
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  <span className="text-primary">{s.winning_trades}</span>
                  <span className="text-muted-foreground">/</span>
                  <span className="text-destructive">{s.losing_trades}</span>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    <ProgressRing value={s.win_rate} size={24} strokeWidth={2.5}>
                      <span className="text-[7px] font-bold">{s.win_rate.toFixed(0)}</span>
                    </ProgressRing>
                    <span>{s.win_rate.toFixed(1)}%</span>
                  </div>
                </TableCell>
                <TableCell className={`text-right ${s.avg_pnl_percent >= 0 ? "text-primary" : "text-destructive"}`}>
                  {s.avg_pnl_percent >= 0 ? "+" : ""}{s.avg_pnl_percent.toFixed(2)}%
                </TableCell>
                <TableCell className={`text-right font-medium ${s.total_pnl >= 0 ? "text-primary" : "text-destructive"}`}>
                  {s.total_pnl >= 0 ? "+" : ""}${s.total_pnl.toFixed(2)}
                </TableCell>
                <TableCell className="text-right text-primary">
                  +${s.best_trade.toFixed(2)}
                </TableCell>
                <TableCell className="text-right text-destructive">
                  ${s.worst_trade.toFixed(2)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Symbol breakdown */}
      {by_symbol.length > 0 && (
        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border/30">
            <h2 className="font-semibold">{t("tabs.symbols")}</h2>
          </div>
          <div className="p-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {by_symbol.map((s) => (
              <div key={s.symbol} className="glass-subtle rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <span className="font-semibold">{s.symbol}</span>
                  <span className={`text-sm font-medium ${s.total_pnl >= 0 ? "text-primary" : "text-destructive"}`}>
                    {s.total_pnl >= 0 ? "+" : ""}${s.total_pnl.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-2">
                  <ProgressRing value={s.win_rate} size={36} strokeWidth={3}>
                    <span className="text-[8px] font-bold">{s.win_rate.toFixed(0)}%</span>
                  </ProgressRing>
                  <div className="text-xs text-muted-foreground">
                    <p>{s.total_trades} {t("symbolsTable.trades").toLowerCase()}</p>
                    <p>{s.win_rate.toFixed(1)}% {t("symbolsTable.winRate").toLowerCase()}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
