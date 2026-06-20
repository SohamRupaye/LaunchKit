# LaunchKit

**One config file. Production-ready output. Zero vendor lock-in.**

LaunchKit bridges the gap between _"it works on my machine"_ and _"it runs in production reliably"_ — without locking you into AWS, GCP, or any managed Platform-as-a-Service (PaaS).

Define your services once. LaunchKit intelligently detects your code, then generates highly-optimized Dockerfiles, Kubernetes manifests, CI/CD pipelines, Nginx proxies, and environment configurations.

```bash
pip install launchkit-cli
launchkit init      # Detects your stack & scaffolds launchkit.yaml
launchkit generate  # Outputs everything you need to deploy
launchkit verify    # PROVES the output: lints, builds, boots, hits /health
launchkit measure   # Sets resource limits from OBSERVED memory, not a guess
```

PyPI publishing is wired up in this repository, but `pip install launchkit-cli` only works after the first release is pushed to PyPI.

---

## What makes it different

Most scaffolding tools — and most LLM prompts — *guess*. They emit a plausible Dockerfile with a hardcoded entrypoint and resource numbers pulled from a lookup table, and you find out whether it works by pushing to CI and waiting.

**LaunchKit proves its output instead of guessing it:**

- **`launchkit verify`** doesn't just write files — it runs `hadolint`, validates every K8s manifest (`kubeconform`), **builds the image, boots the container, and hits your healthcheck**. If the generated Dockerfile won't build or the app won't serve, you find out in seconds, with the container logs and a fix hint — not after a CI round-trip.
- **Real entrypoint detection.** Instead of hardcoding `main:app`, LaunchKit scans your source for the actual ASGI/WSGI callable, Django package, Celery app, or `package.json` start script — and the smoke test proves it boots.
- **`launchkit measure`** builds and runs each service, observes **real peak memory** under a light load, and sets requests/limits from that — rounded to deterministic buckets. A measured floor an LLM simply cannot give you.
- **A deployment linter** that encodes real ops expertise: OOMKill risk, silent readiness failures, CPU autoscaling on I/O-bound workers, single-replica production, and (after `measure`) a `memory_limit` below the observed boot peak.

That's the pitch no on-demand LLM can honestly make: *it didn't just write your Dockerfile — it booted it and proved `/health` returns 200.*

---

## The Problem

Every project hits the same wall:

- Dockerfiles written from scratch every time, missing layer caches and memory limits.
- CI/CD pipelines copy-pasted, taking 20 minutes to run because they lack monorepo caching.
- Kubernetes manifests hand-crafted with no consistency across staging and production.
- Vendor-specific config (ECS task definitions, Cloud Run YAMLs) that traps your infrastructure.
- The dreaded lock-in of platforms like Render, Heroku, or Fly.io that become prohibitively expensive at scale.

LaunchKit gives you the **output files**. You own everything. If you outgrow LaunchKit, you just run `launchkit eject` and keep the pristine files.

---

## How It Works

```text
Your Monorepo / App
    │
    ▼
launchkit.yaml          ← The single source of truth (scaffolded automatically)
    │
    ▼
launchkit generate
    │
    ├── services/                 ← Multi-stage, language-optimized Dockerfiles
    ├── .github/workflows/ci.yml  ← Affected-only monorepo CI/CD pipelines
    ├── nginx/nginx.conf          ← Production-grade reverse proxy with rate limiting
    └── k8s/
        ├── staging/              ← Environment overrides (e.g. 1 replica)
        └── production/
            ├── deployment.yaml   ← Deployments with intelligent resource limits
            ├── hpa.yaml          ← Autoscaling config
            ├── ingress.yaml      ← TLS & DNS setup
            └── secrets-hint.yaml ← Secure guidance for secrets management
    │
    ▼
launchkit verify        ← builds the image, boots it, hits /health — proves it works
launchkit measure       ← observes real memory, sets resource limits from data
```

No magic, no backend services, no runtime dependency. LaunchKit is a **generator + verification layer** — the output is plain files you can read, modify, review, and commit, and it proves those files actually build and boot.

---

## Features (Complexity Eraser)

LaunchKit goes beyond templating: it detects, generates, and then **verifies** — building, booting, and measuring the output so you ship files that actually work.

### Terminal Demo

There is now a reproducible mixed-stack demo flow for asciinema recordings:

```bash
pip install -e ".[dev,release]"
python -m pip install asciinema
bash scripts/record_mixed_stack_demo.sh
```

That script creates a temporary mixed-stack repo, runs `launchkit init`, runs `launchkit generate`, and writes a shareable cast to `demo/launchkit-mixed-stack.cast`.

### 1. Stack Auto-Detection (8 Languages Supported)
`launchkit init` scans your dependency and build files (signal-based detection) to identify each service's language and framework, then detects its real start command:

| Language | Recognized Frameworks & Build Tools |
|----------|-------------------------------------|
| **Python** | FastAPI, Flask, Django, Starlette, Celery workers |
| **Node.js**| Next.js, Express, Fastify, Koa, NestJS |
| **Go**     | Gin, Echo, Fiber, Chi |
| **Java**   | Spring Boot, Quarkus, Micronaut (Maven & Gradle caching) |
| **Rust**   | Actix, Axum, Rocket, Warp (Cargo-chef layer caching) |
| **Ruby**   | Rails, Sinatra, Sidekiq workers |
| **PHP**    | Laravel, Symfony, Slim (php-fpm + deep OPcache tuning) |
| **.NET**   | ASP.NET, Worker Services (.csproj detection) |

### 2. Environment Profiles
Generate dedicated staging AND production manifests from a single base configuration.

```yaml
environments:
  staging:
    namespace: staging
    domain: staging.myapp.com
    scale: { max: 2 }
  production:
    namespace: production
    domain: myapp.com
    tls: true
    replicas: 2
```
`launchkit generate --env staging` creates a distinct folder safely sandboxed from production configurations.

### 3. `launchkit lint` (Proactive Deployment Advisor)
LaunchKit lints your deployment architecture _before_ you even hit `kubectl apply`.
It catches:
- Missing Healthchecks (Silent readiness failure).
- Memory Request Mismatches (OOMKills during bursting).
- Missing Production Replicas.
- `latest` image tags.
- CPU Autoscaling on I/O-bound (async) workers.

### 4. `launchkit eject` (Trust & Zero Lock-in)
The ultimate trust signal. When you want to take over infrastructure customization entirely:
```bash
launchkit eject --yes
```
This strips all `# Generated by LaunchKit` headers and K8s annotations, deletes `launchkit.yaml`, and leaves you with pristine, independent files.

### 5. `launchkit upgrade` (Continuous Intelligence)
Dependencies change, new branches are created, and memory usage shifts.
`launchkit upgrade` rescans your source code, compares it against your `launchkit.yaml`, and suggests interactive dependency changes, new resource boundaries, and CI strategy updates.

### 6. Nginx Reverse Proxy
Generated K8s services need an ingress layer. LaunchKit automatically spins up an optimized containerized Nginx reverse proxy including:
- Upstream load balancing
- Gzip compressions
- Rate limiting (`limit_req_zone`)
- Websocket support (`Upgrade` / `Connection`)
- Security Headers (HSTS, nosniff, X-Frame-Options)

### 7. Monorepo "Affected-Only" CI
Tired of waiting 40 minutes for all 8 microservices to build because you changed a markdown file?
LaunchKit generates GitHub Actions and GitLab CI files that compute Git diffs to **only trigger pipelines for the strictly changed services**.

### 8. Resource Profiling — inferred, then *measured*
A Next.js frontend, a Go API, and a Python ML worker don't scale the same way. At `init`, LaunchKit picks a starting resource profile from dependency signals (`pytorch`, `pandas`, `sidekiq`, …) — an honest heuristic, not a promise.

Then `launchkit measure` makes it real: it builds and boots each service, observes **peak memory under a light synthetic load**, and rewrites requests/limits from that observation — rounded up to deterministic buckets with headroom, tagged `source: measured`. The measured value is a **floor for catching under-provisioning** (e.g. a `memory_limit` below the boot peak that would OOMKill on startup), not authoritative production sizing — for that, use production traffic and a tool like VPA.

### 9. Verify — proof, not vibes
`launchkit verify` runs a staged ladder against the generated output. Every external tool self-skips when absent (`launchkit doctor` shows what unlocks more):

| Level | What it does |
|-------|--------------|
| `static` | Deployment linter + YAML/manifest validation + `hadolint` + `kubeconform` (or `kubectl --dry-run`) + `docker compose config` |
| `build`  | `docker build` every service — catches dependency/path bugs |
| `smoke`  | Runs the container and polls the healthcheck — **proves the start command actually boots a serving app** |

On failure you get the container logs and a concrete fix hint. The generated CI pipeline runs `launchkit verify` too, gating the push job — the tool ships its own proof into your repo.

---

## CLI Reference

```bash
launchkit init                    # Detects stack & scaffolds launchkit.yaml (incl. start command)
launchkit generate                # Generates all output files
launchkit generate --env staging  # Generates files specific to 'staging'
launchkit generate --only docker  # Only generate Dockerfiles
launchkit generate --verify       # Generate, then run static verification
launchkit verify                  # Prove the output: lint + validate (static)
launchkit verify --level build    # Also `docker build` every service
launchkit verify --level smoke    # Also boot the container & hit the healthcheck
launchkit measure                 # Observe real memory usage (dry-run report)
launchkit measure --apply         # Write measured resource buckets into launchkit.yaml
launchkit diff                    # Dry-run: show what would change
launchkit lint                    # Catch deployment & configuration issues early
launchkit validate                # Validate launchkit.yaml schema natively
launchkit doctor                  # Check host tools (docker, kubectl, hadolint, kubeconform…)
launchkit eject                   # Strip markers, leave pristine files, exit LaunchKit
launchkit upgrade                 # Re-run intelligence on codebase & get suggestions
```

Custom templates: drop a `.j2` with the same relative path into `.launchkit/templates/` to override any generated file without ejecting — `verify` still runs against your override.

---

## Why Not Just Use X?

| Tool | The Trade-off |
|------|--------------|
| **Asking an LLM** | Fast, but it *guesses* — a plausible Dockerfile with a hardcoded entrypoint and made-up resource numbers, unverified. LaunchKit detects the real entrypoint, then builds/boots/measures to *prove* it. |
| **Railway / Render / Fly.io** | Incredible DX, but they own your deployment. You're locked into their platform, bandwidth fees, and lacking deep K8s controls. |
| **AWS CDK / Pulumi** | Extremely powerful, but commits you to a specific cloud vendor and requires learning complete Infrastructure-as-Code paradigms. |
| **Helm** | Kubernetes-only templates. Doesn't write your Dockerfiles or CI, and doesn't verify anything builds. |
| **Copilot (AWS)** | AWS-ECS specific. High friction to migrate out. |
| **Writing it yourself** | Configuration drift across microservices. Hard to maintain. Takes days of raw YAML authoring per application. |

**LaunchKit is a generator, not a runtime.** It writes your files, drops knowledge into your repository, and then gets out of the way.

---

## Project Architecture

```text
launchkit/
├── src/launchkit/
│   ├── cli.py                    # Click-based CLI
│   ├── core/                     # Engines: engine, diff, lint, verify, measure, eject, upgrade, doctor, tooling
│   ├── detectors/                # 8 language profilers + entrypoint + environment + resources
│   ├── generators/               # Docker, K8s, CI, Compose, Secrets, Nginx writers
│   ├── templates/                # Jinja2 definitions (overridable via .launchkit/templates/)
│   └── utils/                    # Template loader + thread-safe CLI printers
├── tests/
│   ├── unit/                     # Deterministic tests across detectors, generators, verify, measure
│   └── integration/             # Full pipeline + docker-gated build/smoke/measure tests
├── docs/
└── examples/
    ├── mixed-stack/              # Python API + Next.js frontend + Go worker repo
    └── monorepo-python/
```

---

## Contributing

Contributions are strongly welcomed. The current test suite collects `315 tests`.

If you want to help harden LaunchKit against real codebases, use the validation loop in [docs/real-world-validation.md](./docs/real-world-validation.md) and file results with the repo's real-world validation issue template.

If establishing robust build strategies for new stacks gets you excited, read [docs/adding-a-language.md](./docs/adding-a-language.md) to build new detectors.

---

## License
MIT
