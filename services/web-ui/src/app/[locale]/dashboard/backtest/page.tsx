"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  listStrategies, runBacktest,
  type Strategy, type BacktestResult,
} from "@/lib/api";
import { Sparkline } from "@/components/charts/sparkline";
import { toast } from "sonner";
import { Loader2, TrendingUp, TrendingDown, Target, BarChart3 } from "lucide-react";

export default function BacktestPage() {
  const t = useTranslations("backtest");
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);

  // Form state
  const [strategyId, setStrategyId] = useState("");
  const [symbol, setSymbol] = useState("AAPL");
  const [days, setDays] = useState(90);
  const [capital, setCapital] = useState(10000);
  const [slPct, setSlPct] = useState(2.0);
  const [tpPct, setTpPct] = useState(6.0);
  const [trailing, setTrailing] = useState(false);

  useEffect(() => {
    listStrategies().then((s) => {
      setStrategies(s);
      if (s.length > 0) setStrategyId(s[0].name);
    }).catch(() => {});
  }, []);

  async function handleRun() {
    if (!strategyId || !symbol) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await runBacktest({
        strategy_id: strategyId,
        symbol: symbol.toUpperCase(),
        days,
        initial_capital: capital,
        stop_loss_pct: slPct,
        take_profit_pct: tpPct,
        trailing_stop: trailing,
      });
      setResult(res);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Backtest failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>

      {/* Form */}
      <div className="glass rounded-2xl p-5 space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="text-xs text-muted-foreground">{t("strategy")}</label>
            <select
              value={strategyId}
              onChange={(e) => setStrategyId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border/30 bg-background px-3 py-2 text-sm"
            >
              {strategies.map((s) => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-muted-foreground">{t("symbol")}</label>
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="mt-1 rounded-lg"
              placeholder="AAPL"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">{t("days")}</label>
            <Input
              type="number"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="mt-1 rounded-lg"
              min={7}
              max={365}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">{t("capital")}</label>
            <Input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="mt-1 rounded-lg"
              min={100}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">{t("stopLoss")}</label>
            <Input
              type="number"
              value={slPct}
              onChange={(e) => setSlPct(Number(e.target.value))}
              className="mt-1 rounded-lg"
              step={0.5}
              min={0.1}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">{t("takeProfit")}</label>
            <Input
              type="number"
              value={tpPct}
              onChange={(e) => setTpPct(Number(e.target.value))}
              className="mt-1 rounded-lg"
              step={0.5}
              min={0.1}
            />
          </div>
          <div className="flex items-end gap-2">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={trailing}
                onChange={(e) => setTrailing(e.target.checked)}
                className="rounded"
              />
              {t("trailingStop")}
            </label>
          </div>
          <div className="flex items-end">
            <Button
              onClick={handleRun}
              disabled={loading || !strategyId || !symbol}
              className="rounded-lg w-full"
            >
              {loading ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> {t("running")}</>
              ) : (
                t("run")
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Results */}
      {result && (
        <>
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
            <div className="glass rounded-2xl p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <TrendingUp className="h-3.5 w-3.5" />
                {t("totalReturn")}
              </div>
              <div className={`text-xl font-semibold mt-1 ${result.total_return_pct >= 0 ? "text-primary" : "text-destructive"}`}>
                {result.total_return_pct >= 0 ? "+" : ""}{result.total_return_pct}%
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                ${result.initial_capital.toFixed(0)} → ${result.final_capital.toFixed(2)}
              </div>
            </div>
            <div className="glass rounded-2xl p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Target className="h-3.5 w-3.5" />
                {t("winRate")}
              </div>
              <div className="text-xl font-semibold mt-1">{result.win_rate}%</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {result.winning_trades}W / {result.losing_trades}L
              </div>
            </div>
            <div className="glass rounded-2xl p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <BarChart3 className="h-3.5 w-3.5" />
                {t("trades")}
              </div>
              <div className="text-xl font-semibold mt-1">{result.total_trades}</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {t("best")}: +{result.best_trade_pct}% | {t("worst")}: {result.worst_trade_pct}%
              </div>
            </div>
            <div className="glass rounded-2xl p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <TrendingDown className="h-3.5 w-3.5" />
                {t("maxDrawdown")}
              </div>
              <div className={`text-xl font-semibold mt-1 ${result.max_drawdown_pct > 10 ? "text-destructive" : ""}`}>
                {result.max_drawdown_pct}%
              </div>
              {result.sharpe_ratio != null && (
                <div className="text-xs text-muted-foreground mt-0.5">
                  Sharpe: {result.sharpe_ratio}
                </div>
              )}
            </div>
          </div>

          {/* Equity curve */}
          {result.equity_curve.length >= 2 && (
            <div className="glass rounded-2xl overflow-hidden">
              <div className="px-5 py-4 border-b border-border/30">
                <h2 className="font-semibold">{t("equityCurve")}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {result.strategy} — {result.symbol} — {result.start_date?.split("T")[0]} to {result.end_date?.split("T")[0]}
                </p>
              </div>
              <div className="p-5">
                <Sparkline
                  data={result.equity_curve.map((p) => p.equity)}
                  width={800}
                  height={120}
                  color={result.total_return_pct >= 0 ? "oklch(0.75 0.18 160)" : "oklch(0.65 0.2 25)"}
                  className="w-full"
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
