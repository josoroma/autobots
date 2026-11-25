// US-14.13: headless Chromium for one browsing call, and the one door to its DevTools.
//
// Chromium binds DevTools to 127.0.0.1 only, so this forwards 0.0.0.0:9222 on the browser's
// internal network to it. Nothing else listens. Every request Chromium makes goes through the egress
// proxy, loopback included, and nothing is resolved here except the proxy's own name. The container
// is the sandbox: it runs as pwuser with no capabilities, so Chromium's own sandbox can't start.
// If Chromium exits, so does this, and the container with it. If Chromium can't be found or
// started, or the forwarder can't listen, it exits 1 with one line naming why (SQLI-20).
//
// The stealth image sets AUTOBOTS_BROWSER=stealth (Decision 0038 Z2, Z3): the same start, with Google
// Chrome headed on Xvfb. It names no user agent, device or GPU of its own. TZ is the session's.
"use strict";
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");

// A direct write, since process.exit can cut short a pending write to a pipe.
function fail(reason) {
  fs.writeSync(2, `browser-entrypoint: ${reason}\n`);
  process.exit(1);
}

// The one entry of `folder` that `wanted` accepts. Exits if there is none.
function entry(folder, wanted, description) {
  let names = [];
  try {
    names = fs.readdirSync(folder);
  } catch (error) {
    fail(`cannot read ${folder} (${error.code ?? error.message}), so Chromium can't be found`);
  }
  const name = names.find(wanted);
  if (name === undefined) {
    fail(`no ${description} in ${folder}, so Chromium can't be found`);
  }
  return name;
}

// The box's browser: Chrome for Testing, in the Playwright image's own folder.
function chromeForTesting() {
  const root = entry(
    "/ms-playwright",
    (name) => /^chromium-\d+$/.test(name),
    "chromium-<revision> folder",
  );
  const platform = entry(
    `/ms-playwright/${root}`,
    (name) => name.startsWith("chrome-linux"),
    "chrome-linux folder",
  );
  return `/ms-playwright/${root}/${platform}/chrome`;
}

const stealth = process.env.AUTOBOTS_BROWSER === "stealth";
const INTERNAL = 9221;
const DISPLAY = ":99";
const SCREEN = "1440x900x24";

const SOCKET = "/tmp/.X11-unix/X99";
const DISPLAY_MS = 10_000;

// Headed Chrome exits at once without its display, so it starts when Xvfb's socket is there.
function withDisplay(start) {
  const display = spawn("Xvfb", [DISPLAY, "-screen", "0", SCREEN, "-nolisten", "tcp"], {
    stdio: "ignore",
  });
  display.on("error", (error) => fail(`Xvfb did not start: ${error.message}`));
  display.on("exit", (code) => fail(`Xvfb exited with ${code}`));
  const began = Date.now();
  const poll = setInterval(() => {
    if (fs.existsSync(SOCKET)) {
      clearInterval(poll);
      start();
    } else if (Date.now() - began > DISPLAY_MS) {
      fail("Xvfb offered no display in 10 seconds");
    }
  }, 50);
}

// The box is headless. The stealth browser is headed, with software WebGL rather than none.
const SURFACE = stealth
  ? ["--window-size=1440,900", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
  : ["--headless=new", "--disable-gpu"];

// Schemes and methods are refused over CDP by the executor's request guard, downloads by the managed
// policy the image installs, and every connection by the egress proxy.
const FLAGS = [
  ...SURFACE,
  "--no-sandbox",
  `--remote-debugging-port=${INTERNAL}`,
  "--proxy-server=http://proxy:3128",
  "--proxy-bypass-list=<-loopback>",
  "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE proxy",
  "--user-data-dir=/tmp/profile",
  "--disable-dev-shm-usage",
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
];

let chromium = null;
function startBrowser() {
  chromium = spawn(stealth ? "/opt/google/chrome/chrome" : chromeForTesting(), FLAGS, {
    stdio: ["ignore", "inherit", "inherit"],
    env: stealth ? { ...process.env, DISPLAY } : process.env,
  });
  chromium.on("error", (error) => fail(`Chromium did not start: ${error.message}`));
  chromium.on("exit", (code) => process.exit(code ?? 1));
}
if (stealth) withDisplay(startBrowser);
else startBrowser();

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
  .on("error", (error) => fail(`the DevTools forwarder stopped: ${error.message}`))
  .listen(9222, "0.0.0.0");
for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => (chromium ? chromium.kill("SIGTERM") : process.exit(0)));
}
