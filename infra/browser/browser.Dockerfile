# US-14.13, Decision 0018 B1: the official Playwright image for the pinned Playwright (1.64.1),
# by digest. Chromium lives only here, never on the Mac. Built by `make browser-images`, labelled
# with the executor's fingerprint (refactor plan R-57).
FROM mcr.microsoft.com/playwright@sha256:2f05f8a734509a7b3f26a912639488ee08f58a7b292d14d62271bcff9038768f
COPY browser-entrypoint.js /opt/autobots/browser-entrypoint.js
# Decision 0035 Y6: downloads are off by Chromium's managed policy, which code driving the browser
# over CDP can't change. Chrome for Testing reads its policies from this folder.
COPY chromium-policy.json /etc/opt/chrome_for_testing/policies/managed/autobots.json
USER pwuser
ENTRYPOINT ["node", "/opt/autobots/browser-entrypoint.js"]
