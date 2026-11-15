# Local commands for the persistent install. README-SETUP-RUN.md explains them.
# This wraps the guarded scripts and adds no behavior: scripts/persistent_install.py is still
# the only path that changes the database, and nothing here removes a container or a volume.

# Assigned with := on purpose. Make lets the environment override ?=, and runbooks teach PROJECT
# as a shell variable, so an export could otherwise choose another stack or turn on inference.
# These change only when named on the make command line.
PROJECT      := autobots-install
INSTALL_DIR  := $(HOME)/.local/share/autobots-install
WORKSPACE    := Personal
# install.json holds no secret. Its ports win once it exists, so they're only chosen at first-time.
recorded      = $(shell python3.12 scripts/local_app.py recorded "$(INSTALL_DIR)" $(1) 2>/dev/null)
GATEWAY_PORT := $(or $(call recorded,gateway_port),55321)
DB_PORT      := $(or $(call recorded,db_port),55322)
API_PORT     := $(or $(call recorded,api_port),8001)
WEB_PORT     := $(or $(call recorded,web_port),3000)
# Empty means off. Only `enabled` turns on inference, which spends real money.
INFERENCE    :=

# The pinned Node, found and checked as scripts/toolchain.py finds it, or empty. Read only when a recipe uses it.
NODE_BIN  = $(shell python3.12 scripts/toolchain.py node-bin 2>/dev/null)
NO_NODE  := The pinned Node $(shell cat .node-version) was not found on PATH or under nvm. Install it, then: make toolchain
PY       := services/agent/.venv/bin/python
NEXT     := apps/web/node_modules/.bin/next
INSTALL  := $(PY) scripts/persistent_install.py --install-dir "$(INSTALL_DIR)"
APP_ENV  := $(INSTALL_DIR)/app.env
RUN_DIR  := $(INSTALL_DIR)/run
LOG_DIR  := $(INSTALL_DIR)/logs
# Process supervision lives in scripts/local_app.py, which tests/harness/test_local_app.py exercises.
LOCAL_APP = python3.12 scripts/local_app.py --run-dir "$(RUN_DIR)" --log-dir "$(LOG_DIR)"
LAUNCH    = $(LOCAL_APP) start --env-file "$(APP_ENV)" --inference "$(INFERENCE)" --node-bin "$(NODE_BIN)"

.DEFAULT_GOAL := help
# Every sequence here depends on its order, including under an inherited -j.
.NOTPARALLEL:
.PHONY: help first-time toolchain images browser-images install owner build migrate \
	start start-stack start-api start-web start-worker wait-ready \
	stop stop-app stop-web stop-api stop-worker stop-stack status logs check check-fast check-full

help:
	@echo 'First time:'
	@echo '  make first-time   toolchain, images, install, migrations, build and owner'
	@echo 'Every day:'
	@echo '  make start        containers, API, web and worker, with inference off'
	@echo '  make stop         web, API, worker, then containers. Data is kept'
	@echo '  make stop-app     web, API and worker only'
	@echo '  make status       what is listening, and each process'
	@echo '  make logs         follow the API, web and worker logs'
	@echo 'After pulling new code:'
	@echo '  make toolchain    reinstall from the locks'
	@echo '  make build        rebuild the web app'
	@echo '  make migrate      apply pending migrations, after the upgrade runbook'
	@echo 'Paid inference:'
	@echo '  make stop-worker && make start-worker INFERENCE=enabled'
	@echo 'Checks:'
	@echo '  make check        repository checks, with no services'
	@echo '  make check-fast   plus lint, types and unit tests for what changed'
	@echo '  make check-full   plus every lint, type and unit check, the build and browser checks'

# --- First time -------------------------------------------------------------------------

first-time:
	@if [ -f "$(INSTALL_DIR)/install.json" ]; then \
		echo 'An install is already recorded at $(INSTALL_DIR), so there is nothing to set up. Use: make start'; \
		exit 1; \
	fi
	python3.12 scripts/toolchain.py bootstrap
	$(MAKE) images install build owner
	@echo 'Done. Use: make start'

toolchain:
	python3.12 scripts/toolchain.py bootstrap

# The overlay sets pull_policy: never, so these are the only pulls, and only when asked for. Each image the merged
# release and overlay name, so one that upstream adds without an overlay pin is pulled too.
images:
	$(INSTALL) images

# The browser executor's two images, each labelled with the fingerprint of its sources (refactor plan
# R-57, SQLI-02). Built only when asked for. browse_goal stays off until scripts/qualify_browser_executor.py
# passes at that fingerprint, as docs/engineering/runbooks/operations.md says.
browser-images:
	python3.12 scripts/browser_images.py build

install:
	$(INSTALL) init --project $(PROJECT) --gateway-port $(GATEWAY_PORT) --db-port $(DB_PORT) --api-port $(API_PORT) --web-port $(WEB_PORT)
	$(INSTALL) up --project $(PROJECT)
	$(INSTALL) setup --project $(PROJECT)
	$(INSTALL) apply --project $(PROJECT)

# Run once. It creates the owner and a workspace, and refuses an email already in use.
owner:
	@set -a; . "$(APP_ENV)"; . "$(INSTALL_DIR)/owner.env"; set +a; \
		AUTOBOTS_OWNER_PASSWORD="$$OWNER_PASSWORD" PYTHONPATH=services/agent/src \
		$(PY) -m autobots.operations.bootstrap_owner --email "$$OWNER_EMAIL" --workspace-name "$(WORKSPACE)"

build:
	@node_bin='$(NODE_BIN)'; test -n "$$node_bin" || { echo '$(NO_NODE)'; exit 1; }; \
		cd apps/web && PATH="$$node_bin:$$PATH" NEXT_TELEMETRY_DISABLED=1 node_modules/.bin/next build

# Not part of `start`: docs/engineering/runbooks/upgrade.md backs up and tries a copy first.
migrate:
	$(INSTALL) apply --project $(PROJECT)

# --- Start ------------------------------------------------------------------------------

# scripts/local_app.py keeps the rules (SQLI-10). A pid counts only while its start time matches, read
# with a pinned locale and zone, so a pid file that outlived a reboot, or another shell's settings, can't
# make a live worker, possibly a paid one, look stopped. A start is refused beside an untracked copy and
# never stops one. A stop sends TERM and waits out the worker's drain, never KILL, because a step still
# running may be in a paid call. Decisions 0024 K2 and K7 and 0025 V5: --keys gives the API and the
# worker the Tavily and Jina keys, the GitHub repository and token, and AUTOBOTS_BROWSER_EXECUTOR=enabled
# from this repository's .env, parsed as data and never sourced, and nothing else from it. A value saved
# at Settings → Keys & vars still wins for its workspace, and browse_goal still needs a passing executor
# qualification at the current code.

start: start-stack start-api wait-ready start-worker
	@echo 'Open http://127.0.0.1:$(WEB_PORT), and use 127.0.0.1 rather than localhost.'

start-stack:
	$(INSTALL) up --project $(PROJECT)

start-api:
	@$(LAUNCH) api --port $(API_PORT) --keys .env -- $(PY) -m uvicorn --factory autobots.api.main:create_configured_app --host 127.0.0.1 --port $(API_PORT) --no-access-log

start-web:
	@test -f apps/web/.next/BUILD_ID || { echo 'The web app is not built. Use: make build'; exit 1; }
	@test -n '$(NODE_BIN)' || { echo '$(NO_NODE)'; exit 1; }
	@$(LAUNCH) web --port $(WEB_PORT) -- $(NEXT) start apps/web -H 127.0.0.1 -p $(WEB_PORT)

# It settles for 2 seconds, then fails if the worker has already exited.
start-worker:
	@$(LAUNCH) worker --keys .env --settle 2 -- $(PY) -m autobots.operations.worker

# Our own process has to hold the port, and then any HTTP reply will do, as the API answers 401 without
# its credential.
wait-ready: start-web
	@$(LOCAL_APP) await api --port $(API_PORT) --url http://127.0.0.1:$(API_PORT)/
	@$(LOCAL_APP) await web --port $(WEB_PORT) --url http://127.0.0.1:$(WEB_PORT)/

# --- Stop -------------------------------------------------------------------------------

# In this order: nothing new is admitted, then the worker drains, then containers stop. Containers
# stay up if a process wouldn't stop, and -k still signals the others when one of them won't.
stop: stop-app stop-stack

stop-app:
	@$(MAKE) -k --no-print-directory stop-web stop-api stop-worker

stop-web:
	@$(LOCAL_APP) stop web --port $(WEB_PORT)

stop-api:
	@$(LOCAL_APP) stop api --port $(API_PORT)

stop-worker:
	@$(LOCAL_APP) stop worker

# The one stack command outside persistent_install.py, so it checks the recorded project itself.
stop-stack:
	@recorded="$$(python3.12 scripts/local_app.py recorded "$(INSTALL_DIR)" project)" || exit 1; \
	if [ "$$recorded" != "$(PROJECT)" ]; then \
		echo 'Refused: $(PROJECT) is not the recorded install, '"$$recorded"'. Nothing was stopped'; exit 1; \
	fi; \
	docker compose -p "$$recorded" stop

# --- Look -------------------------------------------------------------------------------

status:
	@$(LOCAL_APP) status api web worker
	@$(INSTALL) status --project $(PROJECT)

logs:
	tail -f "$(LOG_DIR)/api.log" "$(LOG_DIR)/web.log" "$(LOG_DIR)/worker.log"

check:
	python3.12 scripts/specs.py validate
	python3.12 scripts/verify.py --profile harness

# The db and operations profiles start disposable Docker projects, so they stay explicit commands.
check-fast:
	python3.12 scripts/verify.py --profile fast

check-full:
	python3.12 scripts/verify.py --profile full
