"use client";

import { useLocale } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { SidebarMenuButton } from "@/components/ui/sidebar";
import { Globe } from "lucide-react";

const LOCALE_LABELS: Record<string, string> = {
  en: "EN",
  es: "ES",
};

export function LocaleSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  function cycleLocale() {
    const idx = routing.locales.indexOf(locale as "en" | "es");
    const next = routing.locales[(idx + 1) % routing.locales.length];
    router.replace(pathname, { locale: next });
  }

  return (
    <SidebarMenuButton
      onClick={cycleLocale}
      className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
      title={`Switch language (${LOCALE_LABELS[locale]})`}
    >
      <Globe className="h-4 w-4" />
    </SidebarMenuButton>
  );
}
