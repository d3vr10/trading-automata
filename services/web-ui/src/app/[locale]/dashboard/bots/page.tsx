"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  listBots, getBotStatus, getEngineHealth, startBot, pauseBot, resumeBot,
  stopBot, deleteBot, type BotConfig,
} from "@/lib/api";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { Play, Pause, Square, Plus, Trash2, Loader2, AlertTriangle, Wifi, WifiOff } from "lucide-react";
import { BotCardSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

const START_TIMEOUT_MS = 30_000;

export default function BotsPage() {
  const t = useTranslations("bots");
  const [bots, setBots] = useState<BotConfig[]>([]);
  const [runtimeStatus, setRuntimeStatus] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<BotConfig | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [engineOnline, setEngineOnline] = useState<boolean | null>(null);
  // Track bots in "starting" state with their timeout handles
  const [startingBots, setStartingBots] = useState<Record<number, boolean>>({});
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRefs = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  const loadStatus = useCallback(async () => {
    try {
      const status = await getBotStatus().catch(() => ({}));
      setRuntimeStatus(status);
      return status;
    } catch {
      return {};
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const [botList, status, health] = await Promise.all([
        listBots().catch(() => []),
        getBotStatus().catch(() => ({})),
        getEngineHealth().catch(() => ({ connected: false, status: "offline" })),
      ]);
      setBots(botList);
      setRuntimeStatus(status);
      setEngineOnline(health.connected);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      Object.values(timeoutRefs.current).forEach(clearTimeout);
    };
  }, [load]);

  // Start/stop polling when there are starting bots
  useEffect(() => {
    const hasStarting = Object.values(startingBots).some(Boolean);
    if (hasStarting && !pollingRef.current) {
      pollingRef.current = setInterval(async () => {
        const status = await loadStatus();
        // Check if any starting bot has transitioned
        setStartingBots((prev) => {
          const next = { ...prev };
          let changed = false;
          for (const [idStr, isStarting] of Object.entries(prev)) {
            if (!isStarting) continue;
            const botId = Number(idStr);
            const bot = bots.find((b) => b.id === botId);
            if (!bot) continue;
            const rs = (status as Record<string, any>)[bot.name];
            if (rs?.running || rs?.error) {
              next[botId] = false;
              changed = true;
              if (timeoutRefs.current[botId]) {
                clearTimeout(timeoutRefs.current[botId]);
                delete timeoutRefs.current[botId];
              }
              if (rs?.error) {
                toast.error(t("startFailed", { error: rs.error }));
              }
            }
          }
          return changed ? next : prev;
        });
      }, 2000);
    } else if (!hasStarting && pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, [startingBots, bots, loadStatus, t]);

  async function handleAction(bot: BotConfig, action: "start" | "pause" | "resume" | "stop") {
    try {
      if (action === "start") {
        await startBot(bot.id);
        // Set starting state with timeout
        setStartingBots((prev) => ({ ...prev, [bot.id]: true }));
        timeoutRefs.current[bot.id] = setTimeout(() => {
          setStartingBots((prev) => {
            if (!prev[bot.id]) return prev;
            toast.error(t("startTimeout"));
            return { ...prev, [bot.id]: false };
          });
        }, START_TIMEOUT_MS);
      } else {
        if (action === "pause") await pauseBot(bot.id);
        else if (action === "resume") await resumeBot(bot.id);
        else await stopBot(bot.id);
        toast.success(t("actionSent", { botName: bot.name, action }));
        setTimeout(load, 1000);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("actionFailed", { action }));
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteBot(deleteTarget.id);
      toast.success(t("botDeleted", { name: deleteTarget.name }));
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete bot");
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
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

  return (
    <div className="space-y-6">
      {/* Engine health banner */}
      {engineOnline !== null && !engineOnline && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          <WifiOff className="h-4 w-4 shrink-0 text-amber-400" />
          <div>
            <span className="font-medium">{t("engineOffline")}</span>
            <span className="ml-1 text-amber-300/80">{t("engineOfflineDescription")}</span>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          {engineOnline && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <Wifi className="h-3 w-3" />
              {t("engineOnline")}
            </span>
          )}
        </div>
        <Button asChild size="sm" className="rounded-xl glow-accent">
          <Link href="/dashboard/bots/new">
            <Plus className="mr-1 h-4 w-4" /> {t("newBot")}
          </Link>
        </Button>
      </div>

      {bots.length === 0 ? (
        <div className="glass rounded-2xl p-8 text-center">
          <p className="text-muted-foreground">{t("noBots")}</p>
          <p className="text-muted-foreground mt-1 text-sm">
            {t("noBotsDescription")}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {bots.map((bot) => {
            const status = runtimeStatus[bot.name] as any;
            const isStarting = !!startingBots[bot.id];
            const isRunning = status?.running && !status?.paused;
            const isPaused = status?.paused;
            const isStopped = !status?.running && !isStarting;
            const hasError = status?.error;

            return (
              <div key={bot.id} className="glass rounded-2xl overflow-hidden">
                <div className="flex items-center justify-between px-5 py-4 border-b border-border/30">
                  <Link
                    href={`/dashboard/bots/${bot.id}`}
                    className="text-base font-semibold hover:text-primary transition-colors"
                  >
                    {bot.name}
                  </Link>
                  {isStarting ? (
                    <Badge variant="secondary" className="bg-blue-500/20 text-blue-300 border-blue-500/30">
                      <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                      {t("statusStarting")}
                    </Badge>
                  ) : hasError ? (
                    <Badge variant="destructive" className="bg-red-500/20 text-red-300 border-red-500/30">
                      <AlertTriangle className="mr-1 h-3 w-3" />
                      Error
                    </Badge>
                  ) : (
                    <Badge
                      variant={isPaused ? "secondary" : isRunning ? "default" : "destructive"}
                      className={isRunning ? "bg-primary/20 text-primary border-primary/30" : ""}
                    >
                      {isPaused ? t("statusPaused") : isRunning ? t("statusRunning") : t("statusStopped")}
                    </Badge>
                  )}
                </div>
                <div className="p-5 space-y-4">
                  {/* Error message from engine */}
                  {hasError && (
                    <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-300">
                      {status.error}
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-muted-foreground text-xs">{t("strategy")}</span>
                      <div className="font-medium">{bot.strategy_id}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground text-xs">{t("broker")}</span>
                      <div className="font-medium">{bot.broker_type} / {bot.environment}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground text-xs">{t("allocation")}</span>
                      <div className="font-medium">${bot.allocation.toFixed(2)}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground text-xs">{t("virtualBalance")}</span>
                      <div className="font-medium">${status?.virtual_balance?.toFixed(2) || "—"}</div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {isStarting && (
                      <Button size="sm" className="rounded-lg" disabled>
                        <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> {t("statusStarting")}
                      </Button>
                    )}
                    {isStopped && !isStarting && (
                      <Button
                        size="sm"
                        className="rounded-lg"
                        disabled={engineOnline === false}
                        onClick={() => handleAction(bot, "start")}
                      >
                        <Play className="mr-1 h-3.5 w-3.5" /> {t("start")}
                      </Button>
                    )}
                    {isRunning && (
                      <Button size="sm" variant="secondary" className="rounded-lg" onClick={() => handleAction(bot, "pause")}>
                        <Pause className="mr-1 h-3.5 w-3.5" /> {t("pause")}
                      </Button>
                    )}
                    {isPaused && (
                      <Button size="sm" className="rounded-lg" onClick={() => handleAction(bot, "resume")}>
                        <Play className="mr-1 h-3.5 w-3.5" /> {t("resume")}
                      </Button>
                    )}
                    {status?.running && (
                      <Button size="sm" variant="destructive" className="rounded-lg" onClick={() => handleAction(bot, "stop")}>
                        <Square className="mr-1 h-3.5 w-3.5" /> {t("stop")}
                      </Button>
                    )}
                    {isStopped && !isStarting && (
                      <Button size="sm" variant="ghost" className="rounded-lg hover:text-destructive ml-auto" onClick={() => setDeleteTarget(bot)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
        <AlertDialogContent className="glass-strong border-border/30 rounded-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deleteConfirmTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget && t("deleteConfirmDescription", { name: deleteTarget.name })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-xl">{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="rounded-xl bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleting}
              onClick={handleDelete}
            >
              {t("deleteConfirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
