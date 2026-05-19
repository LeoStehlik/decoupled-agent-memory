#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"

for path in /brain /brain/ /brain-brief /brain-review /brain-health; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "${BASE_URL%/}${path}")"
  if [ "$code" != "200" ] && [ "$code" != "308" ]; then
    echo "UI_SMOKE_FAIL path=$path status=$code" >&2
    exit 1
  fi
done

python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path

for path in Path("static").glob("brain*.html"):
    HTMLParser().feed(path.read_text())

print("UI_SMOKE_OK")
PY
