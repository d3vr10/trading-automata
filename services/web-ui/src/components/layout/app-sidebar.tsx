"use client";

import {
  LayoutDashboard,
  Bot,
  ArrowLeftRight,
  Wallet,
  BarChart3,
  Blocks,
  FlaskConical,
  Settings,
  KeyRound,
  Users,
  LogOut,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/lib/auth";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { LocaleSwitcher } from "@/components/layout/locale-switcher";

export function AppSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const t = useTranslations("sidebar");

  const mainNav = [
    { title: t("dashboard"), href: "/dashboard" as const, icon: LayoutDashboard },
    { title: t("strategies"), href: "/dashboard/strategies" as const, icon: Blocks },
    { title: t("bots"), href: "/dashboard/bots" as const, icon: Bot },
    { title: t("trades"), href: "/dashboard/trades" as const, icon: ArrowLeftRight },
    { title: t("positions"), href: "/dashboard/positions" as const, icon: Wallet },
    { title: t("analytics"), href: "/dashboard/metrics" as const, icon: BarChart3 },
    { title: t("backtest"), href: "/dashboard/backtest" as const, icon: FlaskConical },
  ];

  const settingsNav = [
    { title: t("settings"), href: "/dashboard/settings" as const, icon: Settings },
    { title: t("brokerKeys"), href: "/dashboard/settings/brokers" as const, icon: KeyRound },
  ];

  const adminNav = [
    { title: t("users"), href: "/dashboard/admin/users" as const, icon: Users },
  ];

  return (
    <Sidebar className="border-r-0">
      <SidebarHeader className="px-4 py-4">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
              <polyline points="22,7 13.5,15.5 8.5,10.5 2,17" />
              <polyline points="16,7 22,7 22,13" />
            </svg>
          </div>
          <span className="text-base font-semibold tracking-tight">{t("brand")}</span>
        </Link>
      </SidebarHeader>

      <Separator className="opacity-30" />

      <SidebarContent className="px-2 py-3">
        <SidebarGroup>
          <SidebarGroupLabel className="px-3 text-[11px] font-medium uppercase tracking-widest text-muted-foreground/60">
            {t("trading")}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {mainNav.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      className={isActive ? "glass bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent/50"}
                    >
                      <Link href={item.href}>
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel className="px-3 text-[11px] font-medium uppercase tracking-widest text-muted-foreground/60">
            {t("account")}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {settingsNav.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      className={isActive ? "glass bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent/50"}
                    >
                      <Link href={item.href}>
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {user && (user.role === "root" || user.role === "admin") && (
          <SidebarGroup>
            <SidebarGroupLabel className="px-3 text-[11px] font-medium uppercase tracking-widest text-muted-foreground/60">
              {t("administration")}
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {adminNav.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <SidebarMenuItem key={item.href}>
                      <SidebarMenuButton
                        asChild
                        isActive={isActive}
                        className={isActive ? "glass bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent/50"}
                      >
                        <Link href={item.href}>
                          <item.icon className="h-4 w-4" />
                          <span>{item.title}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className="p-4">
        <Separator className="mb-4 opacity-30" />
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Avatar className="h-8 w-8 border border-border/50">
              <AvatarFallback className="bg-primary/10 text-primary text-xs font-medium">
                {user?.username?.charAt(0).toUpperCase() || "?"}
              </AvatarFallback>
            </Avatar>
            <div className="text-sm">
              <div className="font-medium">{user?.username}</div>
              <div className="text-muted-foreground text-xs capitalize">{user?.role}</div>
            </div>
          </div>
          <div className="flex items-center justify-center gap-1">
            <LocaleSwitcher />
            <SidebarMenuButton
              onClick={logout}
              className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
            >
              <LogOut className="h-4 w-4" />
            </SidebarMenuButton>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
