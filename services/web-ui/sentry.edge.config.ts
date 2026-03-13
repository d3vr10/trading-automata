import * as Sentry from "@sentry/browser";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.ENVIRONMENT ?? "development",
  tracesSampleRate: 0.1,
  sendDefaultPii: false,
});
