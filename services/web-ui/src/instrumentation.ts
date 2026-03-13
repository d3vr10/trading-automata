/**
 * NextJS instrumentation — runs once when the server starts.
 *
 * Registers OpenTelemetry with a Prometheus exporter so NextJS
 * server-side metrics (SSR duration, fetch calls, etc.) are
 * scraped at GET /api/metrics on port 9464.
 *
 * NextJS 16 auto-discovers this file at src/instrumentation.ts.
 */

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("../sentry.server.config");
  }

  if (process.env.NEXT_RUNTIME === "edge") {
    await import("../sentry.edge.config");
  }

  // OpenTelemetry — Node.js only
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { NodeSDK } = await import("@opentelemetry/sdk-node");
    const { PrometheusExporter } = await import(
      "@opentelemetry/exporter-prometheus"
    );
    const { getNodeAutoInstrumentations } = await import(
      "@opentelemetry/auto-instrumentations-node"
    );

    const prometheusExporter = new PrometheusExporter({
      port: 9464,
      host: "0.0.0.0",
    });

    const sdk = new NodeSDK({
      serviceName: "web-ui",
      metricReader: prometheusExporter,
      instrumentations: [
        getNodeAutoInstrumentations({
          // Disable noisy fs instrumentation
          "@opentelemetry/instrumentation-fs": { enabled: false },
          // Keep HTTP and fetch for SSR/API route tracking
          "@opentelemetry/instrumentation-http": { enabled: true },
          "@opentelemetry/instrumentation-undici": { enabled: true },
        }),
      ],
    });

    sdk.start();
  }
}
