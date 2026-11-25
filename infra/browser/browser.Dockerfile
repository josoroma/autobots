# US-14.13, Decision 0018 B1: the official Playwright image for the pinned Playwright (1.65.1),
# by digest. Its Chromium, 159.0.8154.6, carries the fix for CVE-2026-125350; 1.65.0's, 158.0.8127.18,
# doesn't. apps/web pins its own Playwright for its tests. Chromium lives only here, never on the Mac.
# Built by `make browser-images`, labelled with the executor's fingerprint (refactor plan R-57).
FROM mcr.microsoft.com/playwright@sha256:1507cbfc550a63a6b7396791ca4f00df17beb56342d2447b3f106c306f525579
COPY browser-entrypoint.js /opt/autobots/browser-entrypoint.js
# Decision 0035 Y6 and US-17.4: downloads, file selection, the password manager and card and address
# autofill are off by Chromium's managed policy. Code driving the browser over CDP can turn downloads
# back on, so the worker's request guard also cancels any that begins. Chrome for Testing reads its
# policies from this folder.
COPY chromium-policy.json /etc/opt/chrome_for_testing/policies/managed/autobots.json
USER pwuser
ENTRYPOINT ["node", "/opt/autobots/browser-entrypoint.js"]
