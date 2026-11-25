#!/usr/bin/env bash
# Restarts core and api on new images after draining core (see backend/src/darwin/orchestrator/drain.py).
# Runs on the host that runs Compose, from the repository root; `make deploy` calls it there.
set -euo pipefail

WAIT_MIN="${DRAIN_WAIT_MIN:-60}"
# ONLY=api: a change to the site alone (frontend, API) restarts api and leaves core running.
ONLY="${ONLY:-}"
control="data/control"

docker compose --profile run build

if [ "$ONLY" = "api" ]; then
  docker compose --profile run up -d --force-recreate api
  until curl -sf "localhost:${API_PORT:-4730}/api/health" >/dev/null; do sleep 2; done
  echo "api up; core untouched."
  exit 0
fi

if [ -n "$(docker compose --profile run ps --status running -q core)" ]; then
  mkdir -p "$control"
  rm -f "$control/drained"
  touch "$control/drain"
  echo "Waiting for core to drain: the agent's session and the Lichess game in progress end first (at most ${WAIT_MIN} min)."
  deadline=$(( $(date +%s) + WAIT_MIN * 60 ))
  until [ -f "$control/drained" ]; do
    if [ "$(date +%s)" -ge "$deadline" ]; then
      rm -f "$control/drain"
      echo "core did not drain in ${WAIT_MIN} min: nothing restarted, the drain request is withdrawn." >&2
      echo "A core started before draining existed never answers: restart it by hand when quiet." >&2
      exit 1
    fi
    sleep 5
  done
  echo "core drained."
fi

# Recreated even when the image did not change: a drained core only waits to be stopped.
docker compose --profile run up -d --force-recreate core api
until curl -sf "localhost:${API_PORT:-4730}/api/health" >/dev/null; do sleep 2; done
echo "api up; core: $(docker inspect darwin-chess-core-1 --format '{{.State.Status}}, restarts {{.RestartCount}}')"
