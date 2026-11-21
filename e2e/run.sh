#!/usr/bin/env bash
# Full local end-to-end run: web app + bot Worker + a fake Telegram API.
# Uses the real Telegraph API (creates a small test glossary).
# Needs: node 22, python3, Playwright with Chromium (npm i -D playwright && npx playwright install chromium).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${OUT:-$(mktemp -d)}
export OUT CALLS="$OUT/telegram-calls.ndjson"
: > "$CALLS"
pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT

node "$ROOT/e2e/mock-telegram.mjs" "$CALLS" & pids+=($!)
cp -r "$ROOT/web" "$OUT/site" && echo '{ "bot_api": "http://127.0.0.1:8787" }' > "$OUT/site/config.json"
python3 -m http.server 8766 --directory "$OUT/site" >/dev/null 2>&1 & pids+=($!)
(cd "$ROOT/bot" && [ -d node_modules ] || npm ci --silent)
printf 'BOT_TOKEN=123:fake\nTELEGRAM_API=http://127.0.0.1:8899\n' > "$ROOT/bot/.dev.vars"
(cd "$ROOT/bot" && rm -rf .wrangler/state && npx wrangler dev --port 8787 --ip 127.0.0.1 >"$OUT/wrangler.log" 2>&1) & pids+=($!)
for _ in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:8787/ && break; sleep 1; done
curl -fsS http://127.0.0.1:8787/setup >/dev/null
export SECRET=$(python3 -c "import hashlib;print(hashlib.sha256(b'webhook:123:fake').hexdigest()[:48])")
NODE_PATH=$(npm root -g) node "$ROOT/e2e/journey.cjs"
echo "Screenshots and logs: $OUT"
