#!/bin/sh
set -eu

attempt=1
until alembic upgrade head; do
  if [ "$attempt" -ge 15 ]; then
    echo "Database migrations failed after $attempt attempts" >&2
    exit 1
  fi
  echo "Migration attempt $attempt failed; retrying in 2 seconds..." >&2
  attempt=$((attempt + 1))
  sleep 2
done

exec "$@"
