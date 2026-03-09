"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  listBots, getBotStatus, startBot, pauseBot, resumeBot, stopBot,
  deleteBot, type BotConfig,
} from "@/lib/api";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { Play, Pause, Square, Plus, Trash2 } from "lucide-react";
import { BotCardSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

export default function BotsPage() {
  const t = useTranslations("bots");
  const [bots, setBots] = useState<BotConfig[]>([]);
  const [runtimeStatus, setRuntimeStatus] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<BotConfig | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    try {
      const [botList, status] = await Promise.all([
        listBots().catch(() => []),
        getBotStatus().catch(() => ({})),
      ]);
      setBots(botList);
      setRuntimeStatus(status);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleAction(bot: BotConfig, action: "start" | "pause" | "resume" | "stop") {
    try {
      if (action === "start") await startBot(bot.id);
      else if (action === "pause") await pauseBot(bot.id);
      else if (action === "resume") await resumeBot(bot.id);
      else await stopBot(bot.id);
      toast.success(t("actionSent", { botName: bot.name, action }));
      setTimeout(load, 1000);
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
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
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
            const isRunning = status?.running && !status?.paused;
            const isPaused = status?.paused;
            const isStopped = !status?.running;

            return (
              <div key={bot.id} className="glass rounded-2xl overflow-hidden">
                <div className="flex items-center justify-between px-5 py-4 border-b border-border/30">
                  <Link
                    href={`/dashboard/bots/${bot.id}`}
                    className="text-base font-semibold hover:text-primary transition-colors"
                  >
                    {bot.name}
                  </Link>
                  <Badge
                    variant={isPaused ? "secondary" : isRunning ? "default" : "destructive"}
                    className={isRunning ? "bg-primary/20 text-primary border-primary/30" : ""}
                  >
                    {isPaused ? t("statusPaused") : isRunning ? t("statusRunning") : t("statusStopped")}
                  </Badge>
                </div>
                <div className="p-5 space-y-4">
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
                    {isStopped && (
                      <Button size="sm" className="rounded-lg" onClick={() => handleAction(bot, "start")}>
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
                    {isStopped && (
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
