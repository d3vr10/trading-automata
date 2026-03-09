"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { StrategyCardSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";
import { listStrategies, type Strategy } from "@/lib/api";
import { ProgressRing } from "@/components/charts/progress-ring";
import {
  TrendingUp, Activity, BarChart3, Shield, ShieldAlert, ShieldCheck,
  Clock, Zap, ArrowUpDown, Flame, Trophy,
} from "lucide-react";

const CATEGORY_ICONS: Record<string, typeof TrendingUp> = {
  "trend-following": TrendingUp,
  "mean-reversion": ArrowUpDown,
  momentum: Zap,
};

function getRiskConfig(t: (key: string) => string) {
  return {
    low: { icon: ShieldCheck, label: t("riskLow"), color: "text-chart-1" },
    medium: { icon: Shield, label: t("riskMedium"), color: "text-chart-3" },
    high: { icon: ShieldAlert, label: t("riskHigh"), color: "text-destructive" },
  } as Record<string, { icon: typeof Shield; label: string; color: string }>;
}

export default function StrategiesPage() {
  const t = useTranslations("strategies");
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    listStrategies()
      .then(setStrategies)
      .catch(() => setStrategies([]))
      .finally(() => setLoading(false));
  }, []);

  const categories = ["all", ...new Set(strategies.map((s) => s.category))];
  const filtered = filter === "all" ? strategies : strategies.filter((s) => s.category === filter);

  // Sort: sigma series first, then by target_win_rate descending
  const sorted = [...filtered].sort((a, b) => {
    if (a.series === "sigma" && b.series !== "sigma") return -1;
    if (a.series !== "sigma" && b.series === "sigma") return 1;
    return b.target_win_rate - a.target_win_rate;
  });

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <Skeleton className="h-4 w-48 mt-1 bg-accent/40" />
        </div>
        <div className="flex gap-2">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-8 w-20 rounded-xl bg-accent/40" />
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => <StrategyCardSkeleton key={i} />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t("subtitle", { count: strategies.length })}
          </p>
        </div>
      </div>

      {/* Category filters */}
      <div className="flex gap-2 flex-wrap">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilter(cat)}
            className={`px-3 py-1.5 text-sm rounded-xl transition-colors ${
              filter === cat
                ? "bg-primary text-primary-foreground"
                : "glass-subtle text-muted-foreground hover:text-foreground"
            }`}
          >
            {cat === "all" ? t("all") : cat.replace("-", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </button>
        ))}
      </div>

      {/* Strategy cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sorted.map((strategy) => (
          <StrategyCard key={strategy.id} strategy={strategy} t={t} />
        ))}
      </div>
    </div>
  );
}

function StrategyCard({ strategy, t }: { strategy: Strategy; t: (key: string) => string }) {
  const RISK_CONFIG = getRiskConfig(t);
  const CategoryIcon = CATEGORY_ICONS[strategy.category] || Activity;
  const risk = RISK_CONFIG[strategy.risk_level] || RISK_CONFIG.medium;
  const RiskIcon = risk.icon;

  const effectiveWinRate = strategy.stats.win_rate ?? strategy.target_win_rate;
  const isSigma = !!strategy.series;

  return (
    <div className={`glass rounded-2xl overflow-hidden flex flex-col ${isSigma ? "ring-1 ring-primary/20" : ""}`}>
      {/* Header */}
      <div className="px-5 pt-5 pb-3 flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold truncate">{strategy.name}</h3>
            {isSigma && (
              <Badge variant="outline" className="text-[10px] border-primary/30 text-primary shrink-0">
                {t("sigmaSeries")}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{strategy.short_description}</p>
        </div>
        <ProgressRing value={effectiveWinRate} size={52} strokeWidth={4}>
          <span className="text-[11px] font-semibold">{effectiveWinRate.toFixed(0)}%</span>
        </ProgressRing>
      </div>

      {/* Meta tags */}
      <div className="px-5 flex flex-wrap gap-1.5">
        <Badge variant="secondary" className="text-[10px] gap-1">
          <CategoryIcon className="h-3 w-3" />
          {strategy.category.replace("-", " ")}
        </Badge>
        <Badge variant="secondary" className={`text-[10px] gap-1 ${risk.color}`}>
          <RiskIcon className="h-3 w-3" />
          {risk.label}
        </Badge>
        <Badge variant="secondary" className="text-[10px] gap-1">
          <Clock className="h-3 w-3" />
          {strategy.recommended_timeframe}
        </Badge>
        {strategy.long_only && (
          <Badge variant="secondary" className="text-[10px]">{t("longOnly")}</Badge>
        )}
      </div>

      {/* Indicators */}
      <div className="px-5 mt-3">
        <p className="text-[11px] text-muted-foreground/80 line-clamp-2">
          {strategy.indicators.join(" · ")}
        </p>
      </div>

      {/* Stats footer */}
      <div className="mt-auto px-5 py-3 border-t border-border/20 flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1 text-muted-foreground" title="Popularity rank">
          {strategy.stats.popularity_rank <= 2 ? (
            <Flame className="h-3.5 w-3.5 text-chart-3" />
          ) : (
            <Trophy className="h-3.5 w-3.5" />
          )}
          <span>#{strategy.stats.popularity_rank}</span>
        </div>
        <div className="flex items-center gap-1 text-muted-foreground" title={t("totalTrades")}>
          <BarChart3 className="h-3.5 w-3.5" />
          <span>{strategy.stats.total_trades} {t("totalTrades").toLowerCase()}</span>
        </div>
        {strategy.stats.total_pnl !== 0 && (
          <div className={`ml-auto font-medium ${strategy.stats.total_pnl >= 0 ? "text-primary" : "text-destructive"}`}>
            {strategy.stats.total_pnl >= 0 ? "+" : ""}${strategy.stats.total_pnl.toFixed(2)}
          </div>
        )}
        {strategy.stats.active_positions > 0 && (
          <div className="flex items-center gap-1 text-primary">
            <Activity className="h-3.5 w-3.5" />
            <span>{strategy.stats.active_positions} {t("activePositions").toLowerCase()}</span>
          </div>
        )}
      </div>

      {/* Asset classes */}
      <div className="px-5 pb-4 flex gap-1">
        {strategy.asset_classes.map((ac) => (
          <span key={ac} className="text-[10px] px-1.5 py-0.5 rounded bg-accent/50 text-muted-foreground capitalize">
            {ac}
          </span>
        ))}
      </div>
    </div>
  );
}
