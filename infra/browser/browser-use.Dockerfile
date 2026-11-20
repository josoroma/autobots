# US-17.3, Decision 0035 Y8: browser-use 1.0.6 in the isolated box, from the pinned Playwright image (B1) with
# its own uv-locked environment (services/browser-use/uv.lock), apart from the worker's lock. Built by
# `make browser-images` from services/browser-use, labelled with browser-use's own fingerprint. uv comes from
# its official image, by digest, and installs only what the lock names.
FROM ghcr.io/astral-sh/uv@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv
FROM mcr.microsoft.com/playwright@sha256:2f05f8a734509a7b3f26a912639488ee08f58a7b292d14d62271bcff9038768f
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /opt/browser-use
COPY pyproject.toml uv.lock ./
ENV UV_PYTHON=/usr/bin/python3 UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_NO_CACHE=1
RUN uv sync --frozen --no-dev --no-install-project && rm /usr/local/bin/uv
COPY runner.py ./
# Y16 and Decision 0035 Y6: no telemetry, no update check, nothing to Browser Use's cloud.
ENV PATH=/opt/browser-use/.venv/bin:$PATH ANONYMIZED_TELEMETRY=false BH_TELEMETRY=0 BROWSER_USE_NO_UPDATE_CHECK=1 HOME=/tmp
USER pwuser
ENTRYPOINT ["python", "-I", "/opt/browser-use/runner.py"]
