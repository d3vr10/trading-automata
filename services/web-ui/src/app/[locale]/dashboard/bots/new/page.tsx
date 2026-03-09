"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ArrowLeft, Check, Shield, ShieldAlert, ShieldCheck } from "lucide-react";
import { listStrategies, type Strategy } from "@/lib/api";
import { ProgressRing } from "@/components/charts/progress-ring";

const RISK_COLORS: Record<string, string> = {
  low: "text-chart-1",
  medium: "text-chart-3",
  high: "text-destructive",
};

export default function NewBotPage() {
  const t = useTranslations("bots");
  const router = useRouter();

  const [name, setName] = useState("");
  const [broker, setBroker] = useState("alpaca");
  const [environment, setEnvironment] = useState("paper");
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null);
  const [allocation, setAllocation] = useState("10000");
  const [fenceType, setFenceType] = useState("crypto");

  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loadingStrategies, setLoadingStrategies] = useState(true);

  useEffect(() => {
    listStrategies()
      .then(setStrategies)
      .catch(() => setStrategies([]))
      .finally(() => setLoadingStrategies(false));
  }, []);

  function generateYaml(): string {
    const stratId = selectedStrategy?.id || "";
    return `  - name: "${name}"
    enabled: true
    broker:
      type: ${broker}
      environment: ${environment}
    strategy:
      name: ${stratId}
      class: ${selectedStrategy?.class_name || ""}
    portfolio:
      allocated_capital: ${allocation}
    fence:
      type: ${fenceType}`;
  }

  function handleCopyConfig() {
    if (!name || !selectedStrategy) {
      toast.error(t("new.nameRequired"));
      return;
    }
    navigator.clipboard.writeText(generateYaml());
    toast.success(t("new.configCopied"));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" className="rounded-xl" onClick={() => router.push("/dashboard/bots")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">{t("new.title")}</h1>
      </div>

      {/* Strategy Selector */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border/30">
          <h2 className="font-semibold">{t("strategy")}</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {t("new.description")}
          </p>
        </div>
        <div className="p-4">
          {loadingStrategies ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 rounded-xl glass-subtle animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {strategies.map((s) => {
                const isSelected = selectedStrategy?.id === s.id;
                const winRate = s.stats.win_rate ?? s.target_win_rate;
                const RiskIcon = s.risk_level === "low" ? ShieldCheck : s.risk_level === "high" ? ShieldAlert : Shield;
                return (
                  <button
                    key={s.id}
                    onClick={() => setSelectedStrategy(s)}
                    className={`relative text-left p-4 rounded-xl transition-all ${
                      isSelected
                        ? "ring-2 ring-primary bg-primary/5"
                        : "glass-subtle hover:bg-accent/30"
                    }`}
                  >
                    {isSelected && (
                      <div className="absolute top-2 right-2 h-5 w-5 rounded-full bg-primary flex items-center justify-center">
                        <Check className="h-3 w-3 text-primary-foreground" />
                      </div>
                    )}
                    <div className="flex items-center gap-3">
                      <ProgressRing value={winRate} size={40} strokeWidth={3}>
                        <span className="text-[9px] font-bold">{winRate.toFixed(0)}%</span>
                      </ProgressRing>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium text-sm truncate">{s.name}</span>
                          {s.series && (
                            <Badge variant="outline" className="text-[8px] border-primary/30 text-primary px-1 py-0">
                              SIGMA
                            </Badge>
                          )}
                        </div>
                        <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">{s.short_description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-2 text-[10px] text-muted-foreground">
                      <span className={`flex items-center gap-0.5 ${RISK_COLORS[s.risk_level]}`}>
                        <RiskIcon className="h-3 w-3" />
                        {s.risk_level}
                      </span>
                      <span>{s.recommended_timeframe}</span>
                      <span>#{s.stats.popularity_rank}</span>
                      {s.stats.total_trades > 0 && (
                        <span className="ml-auto">{s.stats.total_trades} trades</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Bot Configuration */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border/30">
          <h2 className="font-semibold">{t("new.title")}</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {t("new.currentMethod")}
          </p>
        </div>
        <div className="p-5 space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("new.botName")}</Label>
              <Input
                placeholder={t("new.botNamePlaceholder")}
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-10 bg-input/50 border-border/50 rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("strategy")}</Label>
              <div className={`flex h-10 items-center rounded-xl border px-3 text-sm ${
                selectedStrategy ? "border-primary/40 bg-primary/5" : "border-border/50 bg-input/50 text-muted-foreground"
              }`}>
                {selectedStrategy ? selectedStrategy.name : t("new.comingSoon")}
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("broker")}</Label>
              <select
                className="flex h-10 w-full rounded-xl border border-border/50 bg-input/50 px-3 py-1 text-sm"
                value={broker}
                onChange={(e) => setBroker(e.target.value)}
              >
                <option value="alpaca">Alpaca</option>
                <option value="coinbase">Coinbase</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("new.environment")}</Label>
              <select
                className="flex h-10 w-full rounded-xl border border-border/50 bg-input/50 px-3 py-1 text-sm"
                value={environment}
                onChange={(e) => setEnvironment(e.target.value)}
              >
                <option value="paper">{t("new.paper")}</option>
                <option value="live">{t("new.live")}</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("new.capitalAllocation")}</Label>
              <Input
                type="number"
                placeholder="10000"
                value={allocation}
                onChange={(e) => setAllocation(e.target.value)}
                className="h-10 bg-input/50 border-border/50 rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("fenceType")}</Label>
              <select
                className="flex h-10 w-full rounded-xl border border-border/50 bg-input/50 px-3 py-1 text-sm"
                value={fenceType}
                onChange={(e) => setFenceType(e.target.value)}
              >
                <option value="crypto">{t("new.crypto")}</option>
                <option value="stock">{t("new.stock")}</option>
                <option value="all">{t("new.all")}</option>
              </select>
            </div>
          </div>

          {/* YAML Preview */}
          {name && selectedStrategy && (
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("new.generatedYaml")}</Label>
              <pre className="rounded-xl glass-subtle p-4 text-sm font-mono overflow-x-auto text-primary/80">
                {generateYaml()}
              </pre>
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <Button className="rounded-xl glow-accent" onClick={handleCopyConfig} disabled={!name || !selectedStrategy}>
              {t("new.copyConfig")}
            </Button>
            <Button variant="outline" className="rounded-xl" onClick={() => router.push("/dashboard/bots")}>
              {t("new.cancel")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
