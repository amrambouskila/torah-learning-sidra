#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

POSTGRES_PORT="${SIDRA_POSTGRES_PORT:-5524}"
API_PORT="${SIDRA_API_PORT:-8285}"
FRONTEND_PORT="${SIDRA_FRONTEND_PORT:-5285}"
IMAGE_PREFIX="torah_learning_sidra"

banner() {
  echo
  echo "  Torah Learning Sidra"
  echo "  ===================="
  echo "  Sidra         http://localhost:${FRONTEND_PORT}"
  echo "  API           http://localhost:${API_PORT}"
  echo "  API docs      http://localhost:${API_PORT}/docs"
  echo "  PostgreSQL    localhost:${POSTGRES_PORT}   (db: sidra, sidra_test)"
  echo
}

autoseed() {
  # Seed the catalog only, and only when it is empty. Never `refresh` -- that re-crawls Sefaria
  # and streams ~656 MB. The calendar is the same kind of thing (a year is ~800 calls), so the
  # ledger is reported rather than seeded here.
  command -v uv >/dev/null 2>&1 || return 0

  # The schema has to exist before anything can ask the database a question. `init` is idempotent.
  (cd backend && uv run sidra-db init >/dev/null) || {
    echo "  Could not create the schema; run 'uv run sidra-db init' by hand."
    return 0
  }

  local status
  status="$(cd backend && uv run sidra-db status 2>/dev/null || true)"

  if [[ "${status}" == *"catalog empty"* ]]; then
    echo "  Catalog is empty; seeding from the committed snapshot..."
    (cd backend && uv run sidra-db seed) || echo "  Seeding failed; run 'uv run sidra-db seed' by hand."
  fi
  if [[ "${status}" == *"ledger empty"* ]]; then
    # A copied project folder brings its ledger export but not the Docker volume the database
    # lives in, so this is the step that puts the history back on a new machine. Offline.
    if [[ -f backend/data/ledger.json ]]; then
      echo "  Ledger is empty; importing backend/data/ledger.json..."
      (cd backend && uv run sidra-db import) || echo "  Import failed; run 'uv run sidra-db import' by hand."
    else
      echo "  Ledger is empty and there is no export to import. To build one (needs the network):"
      echo "    cd backend && uv run sidra-db calendar --start 2026-08-24 && uv run sidra-db seed-tracks"
      echo "  Then 'uv run sidra-db export' before copying this folder anywhere."
    fi
  fi
}

start() {
  docker compose up --build -d
  autoseed
  banner
  echo "  Services are running."
  echo
}

remove_images() {
  docker images --format '{{.Repository}}:{{.Tag}}' \
    | grep "^${IMAGE_PREFIX}" \
    | xargs -r docker rmi || true
}

menu() {
  echo "  [r] restart                        [k] stop, keep images"
  echo "  [q] stop, remove project images    [v] full cleanup (volumes too)"
  echo
}

start
while true; do
  menu
  read -r -n 1 -p "  > " choice || { echo; docker compose down; exit 0; }
  echo
  case "$(printf '%s' "${choice}" | tr '[:upper:]' '[:lower:]')" in
    r)
      docker compose down
      start
      ;;
    k)
      docker compose down
      exit 0
      ;;
    q)
      docker compose down --remove-orphans
      remove_images
      exit 0
      ;;
    v)
      docker compose down --volumes --remove-orphans
      remove_images
      exit 0
      ;;
    *)
      echo "  Unrecognised option."
      echo
      ;;
  esac
done
