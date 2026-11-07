// US-14.13: headless Chromium for one browsing call, and the one door to its DevTools.
//
// Chromium binds DevTools to 127.0.0.1 only, so this forwards 0.0.0.0:9222 on the browser's
// internal network to it. Nothing else listens. Every request Chromium makes goes through the egress
// proxy, loopback included, and nothing is resolved here except the proxy's own name. The container
// is the sandbox: it runs as pwuser with no capabilities, so Chromium's own sandbox can't start.
// If Chromium exits, so does this, and the container with it.
"use strict";
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");

// Chrome for Testing in its new headless mode. Schemes, methods and downloads are refused over CDP
// by the executor's request guard, and every connection by the egress proxy.
const root = fs.readdirSync("/ms-playwright").find((name) => /^chromium-\d+$/.test(name));
const platform = fs.readdirSync(`/ms-playwright/${root}`).find((name) => name.startsWith("chrome-linux"));
const shell = `/ms-playwright/${root}/${platform}/chrome`;
const INTERNAL = 9221;

const chromium = spawn(shell, [
  "--headless=new",
  "--no-sandbox",
  `--remote-debugging-port=${INTERNAL}`,
  "--proxy-server=http://proxy:3128",
  "--proxy-bypass-list=<-loopback>",
  "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE proxy",
  "--user-data-dir=/tmp/profile",
  "--disable-dev-shm-usage",
  "--disable-gpu",
  // Playwright's quiet start: no update, sign-in, metrics, field-trial or safe-browsing traffic.
  "--disable-background-networking",
  "--disable-component-update",
  "--disable-component-extensions-with-background-pages",
  "--disable-field-trial-config",
  "--disable-breakpad",
  "--disable-client-side-phishing-detection",
  "--disable-default-apps",
  "--disable-domain-reliability",
  "--disable-features=Translate,MediaRouter,DialMediaRouteProvider,OptimizationHints,CertificateTransparencyComponentUpdater,AutofillServerCommunication,LensOverlay,PrivacySandboxSettings4",
  "--disable-search-engine-choice-screen",
  "--metrics-recording-only",
  "--no-pings",
  "--no-service-autorun",
  "--password-store=basic",
  "--use-mock-keychain",
  "--safebrowsing-disable-auto-update",
  "--disable-sync",
  "--disable-extensions",
  "--no-first-run",
  "--no-default-browser-check",
  "about:blank",
], { stdio: ["ignore", "inherit", "inherit"] });
chromium.on("exit", (code) => process.exit(code ?? 1));

net
  .createServer((client) => {
    const devtools = net.connect(INTERNAL, "127.0.0.1");
    client.pipe(devtools).pipe(client);
    const close = () => {
      client.destroy();
      devtools.destroy();
    };
    client.on("error", close);
    devtools.on("error", close);
  })
  .listen(9222, "0.0.0.0");
for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => chromium.kill("SIGTERM"));
}
