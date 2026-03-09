"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";
import { changePassword } from "@/lib/api";
import { toast } from "sonner";

export default function SettingsPage() {
  const t = useTranslations("settings");
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      toast.error(t("passwordMismatch"));
      return;
    }

    if (newPassword.length < 8) {
      toast.error(t("passwordMinLength"));
      return;
    }

    setLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      toast.success(t("passwordChanged"));
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to change password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>

      {/* Profile card */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border/30">
          <h2 className="font-semibold">{t("profile")}</h2>
          <p className="text-sm text-muted-foreground mt-0.5">{t("profileDescription")}</p>
        </div>
        <div className="p-5 space-y-3 text-sm">
          <div className="flex justify-between items-center rounded-xl glass-subtle p-3">
            <span className="text-muted-foreground">{t("username")}</span>
            <span className="font-medium">{user?.username}</span>
          </div>
          <div className="flex justify-between items-center rounded-xl glass-subtle p-3">
            <span className="text-muted-foreground">{t("email")}</span>
            <span className="font-medium">{user?.email || t("emailNotSet")}</span>
          </div>
          <div className="flex justify-between items-center rounded-xl glass-subtle p-3">
            <span className="text-muted-foreground">{t("role")}</span>
            <span className="font-medium capitalize">{user?.role}</span>
          </div>
        </div>
      </div>

      {/* Change password card */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border/30">
          <h2 className="font-semibold">{t("changePassword")}</h2>
        </div>
        <div className="p-5">
          <form onSubmit={handleChangePassword} className="space-y-4 max-w-md">
            <div className="space-y-2">
              <Label htmlFor="current" className="text-sm text-muted-foreground">{t("currentPassword")}</Label>
              <Input
                id="current"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                className="h-10 bg-input/50 border-border/50 rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new" className="text-sm text-muted-foreground">{t("newPassword")}</Label>
              <Input
                id="new"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                className="h-10 bg-input/50 border-border/50 rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm" className="text-sm text-muted-foreground">{t("confirmPassword")}</Label>
              <Input
                id="confirm"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="h-10 bg-input/50 border-border/50 rounded-xl"
              />
            </div>
            <Button type="submit" className="rounded-xl" disabled={loading}>
              {loading ? t("updating") : t("updatePassword")}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
