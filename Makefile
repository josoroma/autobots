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
recorded      = $(shell python3.12 -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$(INSTALL_DIR)/install.json" $(1) 2>/dev/null)
GATEWAY_PORT := $(or $(call recorded,gateway_port),55321)
DB_PORT      := $(or $(call recorded,db_port),55322)
API_PORT     := $(or $(call recorded,api_port),8001)
WEB_PORT     := $(or $(call recorded,web_port),3000)
# Empty means off. Only `enabled` turns on inference, which spends real money.
INFERENCE    :=

NODE_BIN := $(HOME)/.nvm/versions/node/v$(shell cat .node-version)/bin
PY       := services/agent/.venv/bin/python
NEXT     := apps/web/node_modules/.bin/next
INSTALL  := $(PY) scripts/persistent_install.py --install-dir "$(INSTALL_DIR)"
APP_ENV  := $(INSTALL_DIR)/app.env
RUN_DIR  := $(INSTALL_DIR)/run
LOG_DIR  := $(INSTALL_DIR)/logs

.DEFAULT_GOAL := help
# Every sequence here depends on its order, including under an inherited -j.
.NOTPARALLEL:
.PHONY: help first-time toolchain images install owner build migrate \
	start start-stack start-api start-web start-worker wait-ready \
	stop stop-app stop-web stop-api stop-worker stop-stack status logs check

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

# The overlay sets pull_policy: never, so these are the only pulls, and only when asked for.
images:
	@grep -E '^[[:space:]]+image:' infra/supabase/compose.overlay.yaml | sed -E 's/.*image:[[:space:]]*//' | \
		while read -r image; do docker pull "$$image" || exit 1; done

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
	cd apps/web && PATH="$(NODE_BIN):$$PATH" NEXT_TELEMETRY_DISABLED=1 node_modules/.bin/next build

# Not part of `start`: docs/engineering/runbooks/upgrade.md backs up and tries a copy first.
migrate:
	$(INSTALL) apply --project $(PROJECT)

# --- Start ------------------------------------------------------------------------------

# $(call running,name): the pid file's process is still the one we started. A pid file can outlive
# a reboot, and its pid can then belong to something else, so the pid has to match its start time.
# Sets $$pid. ps formats lstart for the caller's timezone and locale, so both reads pin them: another
# shell's settings mustn't make a live worker, possibly a paid one, look stopped.
start_time = LC_ALL=C TZ=UTC ps -p "$(1)" -o lstart= 2>/dev/null
running = pid="$$(sed -n 1p "$(RUN_DIR)/$(1).pid" 2>/dev/null)"; started="$$($(call start_time,$${pid:-0}))"; [ -n "$$started" ] && [ "$$started" = "$$(sed -n 2p "$(RUN_DIR)/$(1).pid")" ]

# $(strays_name): pids that look like this process without being the tracked one. A copy started
# outside this file, or one whose pid file was lost, would otherwise make the next start fail on its
# port, or run a second worker. The worker pattern's brackets, and dropping this shell's own pid, keep
# the recipe's own command line from matching.
strays_api    = lsof -nP -t -iTCP:$(API_PORT) -sTCP:LISTEN 2>/dev/null
strays_web    = lsof -nP -t -iTCP:$(WEB_PORT) -sTCP:LISTEN 2>/dev/null
strays_worker = pgrep -f 'autobots[.]operations[.]worker' 2>/dev/null | grep -vx "$$$$"
stray_pids    = held="$$($(strays_$(1)) | tr '\n' ' ' | sed 's/ *$$//')"

# Decision 0024 K2: the Tavily and Jina keys from this repository's .env, for the API and the worker.
# The script parses the file as data and prints only those two names, shell-quoted, so evaluating its
# output runs nothing from the file. A blank or missing key prints nothing.
TOOL_KEYS := eval "$$($(PY) scripts/tool_keys_env.py .env)";
# Decision 0024 K7: AUTOBOTS_BROWSER_EXECUTOR=enabled from the same .env, and nothing but that exact
# value. browse_goal still needs a passing executor qualification at the current code.
BROWSER_SWITCH := eval "$$($(PY) scripts/tool_keys_env.py .env --browser-switch)";

# $(call launch,name,command[,keys]): start in the background, with the install's environment, and
# with the tool keys and the browsing switch when keys is given. It refuses beside an untracked copy and never stops one
# itself, as a worker may be in a paid call.
define launch
	@mkdir -p "$(RUN_DIR)" "$(LOG_DIR)"; \
	if $(call running,$(1)); then \
		echo '$(1): already running'; \
	elif $(call stray_pids,$(1)); [ -n "$$held" ]; then \
		echo '$(1): refused. pid '"$$held"' looks like a copy of the $(1) that this install does not track, so a new one would clash with it.'; \
		echo '  See it with: ps -o pid,lstart,command -p '"$$held"; \
		echo '  Stop it with: kill -TERM '"$$held"' (a worker drains for up to 30 seconds), then run this again.'; \
		exit 1; \
	else \
		set -a; . "$(APP_ENV)"; set +a; \
		$(if $(3),$(TOOL_KEYS) $(BROWSER_SWITCH)) \
		PYTHONPATH=services/agent/src PATH="$(NODE_BIN):$$PATH" NEXT_TELEMETRY_DISABLED=1 AUTOBOTS_WORKER_INFERENCE="$(INFERENCE)" \
			nohup $(2) >> "$(LOG_DIR)/$(1).log" 2>&1 < /dev/null & \
		pid=$$!; { echo "$$pid"; $(call start_time,$$pid); } > "$(RUN_DIR)/$(1).pid"; \
		echo '$(1): started'; \
	fi
endef

# $(call await,name,port,url): our own process has to hold the port, so another project's server
# on it doesn't count. Then any HTTP reply will do, as the API answers 401 without its credential.
define await
	@i=0; until { $(call running,$(1)); } && lsof -nP -t -iTCP:$(2) -sTCP:LISTEN 2>/dev/null | grep -qx "$$pid" && curl -s -o /dev/null --max-time 2 "$(3)"; do \
		i=$$((i + 1)); \
		if [ $$i -ge 30 ] || ! { $(call running,$(1)); }; then \
			echo '$(1): not answering at $(3). Something else may hold the port. Read $(LOG_DIR)/$(1).log'; exit 1; \
		fi; \
		sleep 1; \
	done; echo '$(1): answering at $(3)'
endef

start: start-stack start-api wait-ready start-worker
	@echo 'Open http://127.0.0.1:$(WEB_PORT), and use 127.0.0.1 rather than localhost.'

start-stack:
	$(INSTALL) up --project $(PROJECT)

start-api:
	$(call launch,api,$(PY) -m uvicorn --factory autobots.api.main:create_configured_app --host 127.0.0.1 --port $(API_PORT) --no-access-log,keys)

start-web:
	@test -f apps/web/.next/BUILD_ID || { echo 'The web app is not built. Use: make build'; exit 1; }
	$(call launch,web,$(NEXT) start apps/web -H 127.0.0.1 -p $(WEB_PORT))

start-worker:
	$(call launch,worker,$(PY) -m autobots.operations.worker,keys)
	@sleep 2
	@if $(call running,worker); then :; else echo 'worker: exited. Read $(LOG_DIR)/worker.log'; exit 1; fi

wait-ready: start-web
	$(call await,api,$(API_PORT),http://127.0.0.1:$(API_PORT)/)
	$(call await,web,$(WEB_PORT),http://127.0.0.1:$(WEB_PORT)/)

# --- Stop -------------------------------------------------------------------------------

# $(call halt,name): TERM, then wait out the worker's 30 second drain. It never sends KILL,
# because a step still running may be in a paid call. operations.md covers a cut-short drain.
define halt
	@if $(call running,$(1)); then \
		kill -TERM "$$pid"; i=0; \
		while kill -0 "$$pid" 2>/dev/null; do \
			i=$$((i + 1)); \
			if [ $$i -ge 45 ]; then echo '$(1): still running after 45 seconds, pid '"$$pid"'. Read $(LOG_DIR)/$(1).log'; exit 1; fi; \
			sleep 1; \
		done; \
		echo '$(1): stopped'; \
	else \
		echo '$(1): not running'; \
		if $(call stray_pids,$(1)); [ -n "$$held" ]; then \
			echo '$(1): pid '"$$held"' looks like one this install does not track, so it was left running.'; \
			echo '  See it with: ps -o pid,lstart,command -p '"$$held"'. Stop it with: kill -TERM '"$$held"; \
		fi; \
	fi; \
	rm -f "$(RUN_DIR)/$(1).pid"
endef

# In this order: nothing new is admitted, then the worker drains, then containers stop. Containers
# stay up if a process wouldn't stop, and -k still signals the others when one of them won't.
stop: stop-app stop-stack

stop-app:
	@$(MAKE) -k --no-print-directory stop-web stop-api stop-worker

stop-web:
	$(call halt,web)

stop-api:
	$(call halt,api)

stop-worker:
	$(call halt,worker)

# The one stack command outside persistent_install.py, so it checks the recorded project itself.
stop-stack:
	@recorded="$$(python3.12 -c 'import json, sys; print(json.load(open(sys.argv[1]))["project"])' "$(INSTALL_DIR)/install.json")" || exit 1; \
	if [ "$$recorded" != "$(PROJECT)" ]; then \
		echo 'Refused: $(PROJECT) is not the recorded install, '"$$recorded"'. Nothing was stopped'; exit 1; \
	fi; \
	docker compose -p "$$recorded" stop

# --- Look -------------------------------------------------------------------------------

status:
	@if $(call running,api); then echo "api: running, pid $$pid"; else echo 'api: not running'; fi
	@if $(call running,web); then echo "web: running, pid $$pid"; else echo 'web: not running'; fi
	@if $(call running,worker); then echo "worker: running, pid $$pid"; else echo 'worker: not running'; fi
	@$(INSTALL) status --project $(PROJECT)

logs:
	tail -f "$(LOG_DIR)/api.log" "$(LOG_DIR)/web.log" "$(LOG_DIR)/worker.log"

check:
	python3.12 scripts/specs.py validate
	python3.12 scripts/verify.py --profile harness
