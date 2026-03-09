import createMiddleware from "next-intl/middleware";
import { NextResponse, type NextRequest } from "next/server";
import { routing } from "@/i18n/routing";

const intlMiddleware = createMiddleware(routing);

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip locale handling for API routes and static assets
  if (pathname.startsWith("/api") || pathname.startsWith("/_next") || pathname.startsWith("/favicon")) {
    return NextResponse.next();
  }

  // Apply intl middleware (handles locale detection + prefix)
  const response = intlMiddleware(request);

  // After intl middleware resolves the locale, check auth for dashboard routes
  // Extract locale from the resolved URL
  const resolvedPathname = response instanceof NextResponse
    ? new URL(response.headers.get("location") || request.url).pathname
    : pathname;

  const localeMatch = resolvedPathname.match(/^\/(en|es)/);
  const locale = localeMatch ? localeMatch[1] : routing.defaultLocale;

  // Check auth for dashboard routes
  const isDashboard = resolvedPathname.includes("/dashboard");
  if (isDashboard) {
    const hasSession = request.cookies.has("refresh_token");
    if (!hasSession) {
      const loginUrl = new URL(`/${locale}/login`, request.url);
      loginUrl.searchParams.set("from", resolvedPathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
