"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  listCredentials, createCredential, deleteCredential, updateCredential, type BrokerCredential,
} from "@/lib/api";
import { toast } from "sonner";
import { KeyRound, Plus, Trash2, RefreshCw } from "lucide-react";
import { CredentialSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

export default function BrokersPage() {
  const t = useTranslations("settings");
  const [credentials, setCredentials] = useState<BrokerCredential[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  const [brokerType, setBrokerType] = useState("alpaca");
  const [environment, setEnvironment] = useState("paper");
  const [apiKey, setApiKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [label, setLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [rotateTarget, setRotateTarget] = useState<BrokerCredential | null>(null);
  const [rotateApiKey, setRotateApiKey] = useState("");
  const [rotateSecretKey, setRotateSecretKey] = useState("");
  const [rotatePassphrase, setRotatePassphrase] = useState("");
  const [rotating, setRotating] = useState(false);

  async function load() {
    try {
      const data = await listCredentials();
      setCredentials(data);
    } catch {
      setCredentials([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createCredential({
        broker_type: brokerType,
        environment,
        api_key: apiKey,
        secret_key: secretKey,
        passphrase: passphrase || undefined,
        label,
      });
      toast.success(t("brokers.credentialSaved"));
      setDialogOpen(false);
      resetForm();
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save credential");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteCredential(id);
      toast.success(t("brokers.credentialDeleted"));
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  async function handleRotate(e: React.FormEvent) {
    e.preventDefault();
    if (!rotateTarget) return;
    setRotating(true);
    try {
      await updateCredential(rotateTarget.id, {
        api_key: rotateApiKey || undefined,
        secret_key: rotateSecretKey || undefined,
        passphrase: rotatePassphrase || undefined,
      });
      toast.success(t("brokers.keysRotated"));
      setRotateTarget(null);
      setRotateApiKey("");
      setRotateSecretKey("");
      setRotatePassphrase("");
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to rotate keys");
    } finally {
      setRotating(false);
    }
  }

  function resetForm() {
    setBrokerType("alpaca");
    setEnvironment("paper");
    setApiKey("");
    setSecretKey("");
    setPassphrase("");
    setLabel("");
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-7 w-40 bg-accent/60" />
          <Skeleton className="h-9 w-24 rounded-xl bg-accent/50" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 3 }, (_, i) => <CredentialSkeleton key={i} />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("brokers.title")}</h1>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-xl glow-accent"><Plus className="mr-2 h-4 w-4" /> {t("brokers.addKey")}</Button>
          </DialogTrigger>
          <DialogContent className="glass-strong border-border/30 rounded-2xl">
            <DialogHeader>
              <DialogTitle>{t("brokers.dialog.title")}</DialogTitle>
              <DialogDescription className="text-muted-foreground">
                {t("brokers.description")}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-sm text-muted-foreground">{t("brokers.dialog.brokerType")}</Label>
                  <Select value={brokerType} onValueChange={(v) => { setBrokerType(v); if (v === "coinbase") setEnvironment("live"); }}>
                    <SelectTrigger className="h-10 w-full rounded-xl border-border/50 bg-input/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="glass-strong border-border/30 rounded-xl">
                      <SelectItem value="alpaca">{t("brokers.dialog.alpaca")}</SelectItem>
                      <SelectItem value="coinbase">{t("brokers.dialog.coinbase")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-sm text-muted-foreground">{t("brokers.dialog.env")}</Label>
                  <Select value={brokerType === "coinbase" ? "live" : environment} onValueChange={setEnvironment} disabled={brokerType === "coinbase"}>
                    <SelectTrigger className="h-10 w-full rounded-xl border-border/50 bg-input/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="glass-strong border-border/30 rounded-xl">
                      <SelectItem value="paper">{t("brokers.dialog.paper")}</SelectItem>
                      <SelectItem value="live">{t("brokers.dialog.live")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("brokers.dialog.labelField")}</Label>
                <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder={t("brokers.dialog.labelPlaceholder")} required className="h-10 bg-input/50 border-border/50 rounded-xl" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("brokers.dialog.apiKeyField")}</Label>
                <Input value={apiKey} onChange={(e) => setApiKey(e.target.value)} required className="h-10 bg-input/50 border-border/50 rounded-xl" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("brokers.dialog.secretKey")}</Label>
                <Input type="password" value={secretKey} onChange={(e) => setSecretKey(e.target.value)} required className="h-10 bg-input/50 border-border/50 rounded-xl" />
              </div>
              {brokerType === "coinbase" && (
                <div className="space-y-2">
                  <Label className="text-sm text-muted-foreground">{t("brokers.dialog.passphrase")}</Label>
                  <Input type="password" value={passphrase} onChange={(e) => setPassphrase(e.target.value)} className="h-10 bg-input/50 border-border/50 rounded-xl" />
                </div>
              )}
              <Button type="submit" className="w-full rounded-xl glow-accent" disabled={submitting}>
                {submitting ? t("brokers.dialog.saving") : t("brokers.dialog.save")}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {credentials.length === 0 ? (
        <div className="glass rounded-2xl flex flex-col items-center gap-3 py-12">
          <div className="h-12 w-12 rounded-2xl bg-muted/50 flex items-center justify-center">
            <KeyRound className="text-muted-foreground h-6 w-6" />
          </div>
          <p className="text-muted-foreground">{t("brokers.noKeys")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {credentials.map((cred) => (
            <div key={cred.id} className="glass rounded-2xl flex items-center justify-between p-5">
              <div className="flex items-center gap-4">
                <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
                  <KeyRound className="text-primary h-5 w-5" />
                </div>
                <div>
                  <div className="font-medium">{cred.label}</div>
                  <div className="text-muted-foreground text-sm">
                    {cred.broker_type} / {cred.environment}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant="outline" className="border-border/50 text-muted-foreground font-mono text-xs">{cred.api_key_masked}</Badge>
                <Button variant="ghost" size="sm" className="rounded-lg hover:text-primary" onClick={() => setRotateTarget(cred)} title={t("brokers.rotateKeys")}>
                  <RefreshCw className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="sm" className="rounded-lg hover:text-destructive" onClick={() => handleDelete(cred.id)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Rotate Keys Dialog */}
      <Dialog open={!!rotateTarget} onOpenChange={(open) => { if (!open) setRotateTarget(null); }}>
        <DialogContent className="glass-strong border-border/30 rounded-2xl">
          <DialogHeader>
            <DialogTitle>{t("brokers.rotateKeys")}</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              {rotateTarget && t("brokers.rotateDescription", { label: rotateTarget.label })}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleRotate} className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("brokers.dialog.apiKeyField")}</Label>
              <Input value={rotateApiKey} onChange={(e) => setRotateApiKey(e.target.value)} placeholder={t("brokers.rotateKeepExisting")} className="h-10 bg-input/50 border-border/50 rounded-xl" />
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("brokers.dialog.secretKey")}</Label>
              <Input type="password" value={rotateSecretKey} onChange={(e) => setRotateSecretKey(e.target.value)} placeholder={t("brokers.rotateKeepExisting")} className="h-10 bg-input/50 border-border/50 rounded-xl" />
            </div>
            {rotateTarget?.broker_type === "coinbase" && (
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("brokers.dialog.passphrase")}</Label>
                <Input type="password" value={rotatePassphrase} onChange={(e) => setRotatePassphrase(e.target.value)} placeholder={t("brokers.rotateKeepExisting")} className="h-10 bg-input/50 border-border/50 rounded-xl" />
              </div>
            )}
            <p className="text-xs text-muted-foreground">{t("brokers.rotateHint")}</p>
            <Button type="submit" className="w-full rounded-xl glow-accent" disabled={rotating || (!rotateApiKey && !rotateSecretKey && !rotatePassphrase)}>
              {rotating ? t("brokers.dialog.saving") : t("brokers.rotateKeys")}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
