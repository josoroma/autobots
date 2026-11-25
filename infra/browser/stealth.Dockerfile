# US-20.1, Decision 0038 Z2: real Google Chrome, headed under Xvfb, in an image of its own from the same
# pinned Playwright image (B1). Chrome's .deb is fetched by exact version and SHA-256 and unpacked, so
# none of its install scripts run and no package source is added. Building this accepts Google's terms
# for Chrome. Its 158.0.8127.88 carries the fix for CVE-2026-125350. Built by `make browser-images`,
# labelled with the stealth browser's own fingerprint.
FROM mcr.microsoft.com/playwright@sha256:1507cbfc550a63a6b7396791ca4f00df17beb56342d2447b3f106c306f525579 AS chrome
ADD --checksum=sha256:6c7439981240ba7fb05c3534b4aa3ea3104ce388f300c2bbdf66884f8c554098 \
  https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_158.0.8127.88-1_arm64.deb \
  /tmp/chrome.deb
RUN dpkg -x /tmp/chrome.deb /chrome

FROM mcr.microsoft.com/playwright@sha256:1507cbfc550a63a6b7396791ca4f00df17beb56342d2447b3f106c306f525579
COPY --from=chrome /chrome/opt/google/chrome /opt/google/chrome
COPY browser-entrypoint.js /opt/autobots/browser-entrypoint.js
# The box's policy (Decision 0035 Y6), where Google Chrome reads it.
COPY chromium-policy.json /etc/opt/chrome/policies/managed/autobots.json
ENV AUTOBOTS_BROWSER=stealth
USER pwuser
ENTRYPOINT ["node", "/opt/autobots/browser-entrypoint.js"]
