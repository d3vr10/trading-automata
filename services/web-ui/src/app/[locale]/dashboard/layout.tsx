"use client";

import { useEffect } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AuthProvider, useAuth } from "@/lib/auth";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useWebSocket } from "@/hooks/use-websocket";
import { Wifi, WifiOff } from "lucide-react";

function ConnectionStatus() {
  const { isConnected, retryCount } = useWebSocket();

  if (isConnected) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-emerald-400" title="Real-time updates active">
        <Wifi className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Live</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 text-xs text-amber-400 animate-pulse" title={`Reconnecting... (attempt ${retryCount})`}>
      <WifiOff className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">
        {retryCount > 0 ? `Reconnecting (${retryCount})...` : "Connecting..."}
      </span>
    </div>
  );
}

function DashboardGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const t = useTranslations("common");

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span className="text-sm text-muted-foreground">{t("loading")}</span>
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <SidebarProvider>
      <AppSidebar />
      <main className="flex-1 flex flex-col min-h-screen">
        <header className="sticky top-0 z-30 flex h-12 items-center gap-3 px-4 glass-subtle">
          <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
          <div className="ml-auto">
            <ConnectionStatus />
          </div>
        </header>
        <div className="flex-1 p-6">{children}</div>
      </main>
    </SidebarProvider>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <DashboardGuard>{children}</DashboardGuard>
    </AuthProvider>
  );
}
