#!/usr/bin/env bash
set -e
PORT="${PORT:-3000}"
echo "Starting Next.js frontend on 0.0.0.0:${PORT}..."
exec npx next start -p "${PORT}" -H 0.0.0.0
