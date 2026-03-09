"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getBotStatus, pauseBot, resumeBot, stopBot } from "@/lib/api";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { BotCardSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

export default function BotsPage() {
  const t = useTranslations("bots");
  const [bots, setBots] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const data = await getBotStatus();
      setBots(data);
    } catch {
      setBots({});
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleAction(botName: string, action: "pause" | "resume" | "stop") {
    try {
      if (action === "pause") await pauseBot(botName);
      else if (action === "resume") await resumeBot(botName);
      else await stopBot(botName);
      toast.success(t("actionSent", { botName, action }));
      setTimeout(load, 1000);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("actionFailed", { action }));
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-7 w-20 bg-accent/60" />
          <Skeleton className="h-9 w-24 rounded-xl bg-accent/50" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => <BotCardSkeleton key={i} />)}
        </div>
      </div>
    );
  }

  const botEntries = Object.entries(bots);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <Button asChild size="sm" className="rounded-xl glow-accent">
          <Link href="/dashboard/bots/new">
            <Plus className="mr-1 h-4 w-4" /> {t("newBot")}
          </Link>
        </Button>
      </div>

      {botEntries.length === 0 ? (
        <div className="glass rounded-2xl p-8 text-center">
          <p className="text-muted-foreground">{t("noBots")}</p>
          <p className="text-muted-foreground mt-1 text-sm">
            {t("noBotsDescription")}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {botEntries.map(([name, status]: [string, any]) => (
            <div key={name} className="glass rounded-2xl overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-border/30">
                <Link
                  href={`/dashboard/bots/${encodeURIComponent(name)}`}
                  className="text-base font-semibold hover:text-primary transition-colors"
                >
                  {name}
                </Link>
                <Badge
                  variant={status.paused ? "secondary" : status.running ? "default" : "destructive"}
                  className={status.running && !status.paused ? "bg-primary/20 text-primary border-primary/30" : ""}
                >
                  {status.paused ? t("statusPaused") : status.running ? t("statusRunning") : t("statusStopped")}
                </Badge>
              </div>
              <div className="p-5 space-y-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground text-xs">{t("broker")}</span>
                    <div className="font-medium">{status.broker || "N/A"}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">{t("fenceType")}</span>
                    <div className="font-medium">{status.fence_type || "N/A"}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">{t("allocation")}</span>
                    <div className="font-medium">${status.allocation?.toFixed(2) || "0"}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">{t("balance")}</span>
                    <div className="font-medium">${status.virtual_balance?.toFixed(2) || "0"}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  {status.running && !status.paused && (
                    <Button size="sm" variant="secondary" className="rounded-lg" onClick={() => handleAction(name, "pause")}>
                      {t("pause")}
                    </Button>
                  )}
                  {status.paused && (
                    <Button size="sm" className="rounded-lg" onClick={() => handleAction(name, "resume")}>
                      {t("resume")}
                    </Button>
                  )}
                  {status.running && (
                    <Button size="sm" variant="destructive" className="rounded-lg" onClick={() => handleAction(name, "stop")}>
                      {t("stop")}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
