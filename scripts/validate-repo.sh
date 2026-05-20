#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

required=(README.md LICENSE Makefile .env.example docker-compose.yml)
for file in "${required[@]}"; do
  if [[ ! -s "$file" ]]; then
    echo "missing or empty required file: $file" >&2
    exit 1
  fi
done

while IFS= read -r script; do
  bash -n "$script"
done < <(find scripts -maxdepth 1 -type f -name '*.sh' | sort)

python3 -m compileall -q overlays/api overlays/mcp

POSTGRES_PASSWORD=validation-password SUPABASE_JWT_SECRET=validation-secret SUPABASE_ANON_KEY=validation-anon-key NEXT_PUBLIC_SUPABASE_ANON_KEY=validation-anon-key docker compose -f docker-compose.yml config -q

echo "sovereign brain repo validation passed"
