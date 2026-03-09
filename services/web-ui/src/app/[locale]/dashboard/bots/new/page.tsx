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
import {
  listStrategies, listCredentials, createBot,
  type Strategy, type BrokerCredential,
} from "@/lib/api";
import { ProgressRing } from "@/components/charts/progress-ring";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

const RISK_COLORS: Record<string, string> = {
  low: "text-chart-1",
  medium: "text-chart-3",
  high: "text-destructive",
};

export default function NewBotPage() {
  const t = useTranslations("bots");
  const router = useRouter();

  const [name, setName] = useState("");
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null);
  const [credentialId, setCredentialId] = useState("");
  const [allocation, setAllocation] = useState("10000");
  const [fenceType, setFenceType] = useState("hard");
  const [stopLoss, setStopLoss] = useState("2.0");
  const [takeProfit, setTakeProfit] = useState("6.0");
  const [maxPositionSize, setMaxPositionSize] = useState("0.1");

  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [credentials, setCredentials] = useState<BrokerCredential[]>([]);
  const [loadingStrategies, setLoadingStrategies] = useState(true);
  const [loadingCredentials, setLoadingCredentials] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listStrategies()
      .then(setStrategies)
      .catch(() => setStrategies([]))
      .finally(() => setLoadingStrategies(false));
    listCredentials()
      .then(setCredentials)
      .catch(() => setCredentials([]))
      .finally(() => setLoadingCredentials(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedStrategy || !credentialId) {
      toast.error(t("new.validationError"));
      return;
    }
    setSubmitting(true);
    try {
      await createBot({
        name,
        strategy_id: selectedStrategy.id,
        credential_id: Number(credentialId),
        allocation: Number(allocation),
        fence_type: fenceType,
        stop_loss_pct: Number(stopLoss),
        take_profit_pct: Number(takeProfit),
        max_position_size: Number(maxPositionSize),
      });
      toast.success(t("new.botCreated", { name }));
      router.push("/dashboard/bots");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create bot");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" className="rounded-xl" onClick={() => router.push("/dashboard/bots")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-semibold tracking-tight">{t("new.title")}</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Strategy Selector */}
        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border/30">
            <h2 className="font-semibold">{t("strategy")}</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              {t("new.selectStrategy")}
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
                      type="button"
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
            <h2 className="font-semibold">{t("new.configuration")}</h2>
          </div>
          <div className="p-5 space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("new.botName")}</Label>
                <Input
                  placeholder={t("new.botNamePlaceholder")}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  pattern="^[a-zA-Z0-9_-]+$"
                  className="h-10 bg-input/50 border-border/50 rounded-xl"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("new.brokerCredential")}</Label>
                {loadingCredentials ? (
                  <div className="h-10 rounded-xl glass-subtle animate-pulse" />
                ) : credentials.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-2">{t("new.noCredentials")}</p>
                ) : (
                  <Select value={credentialId} onValueChange={setCredentialId}>
                    <SelectTrigger className="h-10 w-full rounded-xl border-border/50 bg-input/50">
                      <SelectValue placeholder={t("new.selectCredential")} />
                    </SelectTrigger>
                    <SelectContent className="glass-strong border-border/30 rounded-xl">
                      {credentials.map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>
                          {c.label} ({c.broker_type} / {c.environment})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("new.capitalAllocation")}</Label>
                <Input
                  type="number"
                  placeholder="10000"
                  value={allocation}
                  onChange={(e) => setAllocation(e.target.value)}
                  required
                  min="1"
                  step="0.01"
                  className="h-10 bg-input/50 border-border/50 rounded-xl"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("fenceType")}</Label>
                <Select value={fenceType} onValueChange={setFenceType}>
                  <SelectTrigger className="h-10 w-full rounded-xl border-border/50 bg-input/50">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="glass-strong border-border/30 rounded-xl">
                    <SelectItem value="hard">{t("new.fenceHard")}</SelectItem>
                    <SelectItem value="soft">{t("new.fenceSoft")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Risk Parameters */}
            <div>
              <Label className="text-sm text-muted-foreground font-medium">{t("new.riskParameters")}</Label>
              <div className="grid gap-4 sm:grid-cols-3 mt-2">
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">{t("new.stopLoss")}</Label>
                  <Input
                    type="number"
                    value={stopLoss}
                    onChange={(e) => setStopLoss(e.target.value)}
                    min="0.1"
                    step="0.1"
                    className="h-9 bg-input/50 border-border/50 rounded-xl text-sm"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">{t("new.takeProfit")}</Label>
                  <Input
                    type="number"
                    value={takeProfit}
                    onChange={(e) => setTakeProfit(e.target.value)}
                    min="0.1"
                    step="0.1"
                    className="h-9 bg-input/50 border-border/50 rounded-xl text-sm"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">{t("new.maxPositionSize")}</Label>
                  <Input
                    type="number"
                    value={maxPositionSize}
                    onChange={(e) => setMaxPositionSize(e.target.value)}
                    min="0.01"
                    step="0.01"
                    max="1"
                    className="h-9 bg-input/50 border-border/50 rounded-xl text-sm"
                  />
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <Button
                type="submit"
                className="rounded-xl glow-accent"
                disabled={submitting || !name || !selectedStrategy || !credentialId}
              >
                {submitting ? t("new.creating") : t("new.create")}
              </Button>
              <Button type="button" variant="outline" className="rounded-xl" onClick={() => router.push("/dashboard/bots")}>
                {t("new.cancel")}
              </Button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
