# Product Demo

The demo shows the core product loop:

```text
raw notes -> maintained synthesis -> graph references -> health status
```

## Run It

```bash
cp .env.example .env
# edit .env placeholders

docker compose up -d --build

BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make demo
```

The demo imports `examples/demo-corpus/sources` as raw evidence and `examples/demo-corpus/synthesis` as maintained pages under `/wiki/synthesis/`.

## What To Look For

After the run, open:

```text
http://KOBE_IP/brain-health
```

Paste a bearer token and inspect. For the demo user, run `./scripts/get-token.sh` with the same `BASE_URL`, `EMAIL`, and `PASSWORD` values used during bootstrap.

- source document count
- synthesis page count
- reference edges
- duplicate active paths
- stale synthesis pages
- uncited source queue

A good demo state has zero duplicate paths and zero stale synthesis pages. Some uncited sources are acceptable if they are intentionally not part of synthesis yet.

## Why This Demo Works

The sample corpus is deliberately small. The point is not storage volume. The point is that a human can see whether the compiled brain is current enough to trust.

## Review Demo

Run `make review-demo` after the stack is up to see the full trust loop:

```text
baseline source-backed synthesis -> newer source evidence -> review queue -> reviewed synthesis -> healthy again
```

The human page is served at `/brain-review`.
