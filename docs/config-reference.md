# launchkit.yaml — Full Reference

## `project`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Project name. Used in K8s labels and image tags. |
| `registry` | string | ✅ | Container registry prefix. e.g. `ghcr.io/yourname/myapp` |

---

## `services`

Each key under `services` is a service name. Values:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lang` | `python` \| `node` \| `go` | — | **Required.** Language runtime. |
| `framework` | string | `null` | Detected framework. Affects Dockerfile CMD and base image. |
| `port` | int | `null` | HTTP port the service listens on. Omit for workers. |
| `type` | `web` \| `worker` | `web` | `worker` = background process, no port, no Service manifest. |
| `healthcheck` | string | `null` | HTTP path for liveness/readiness probes. e.g. `/health` |
| `env_file` | string | `null` | Env file referenced in docker-compose and K8s secret hint. |
| `depends_on` | list[string] | `[]` | Services/infra to wait for in docker-compose. |
| `scale` | ScaleConfig | see below | Autoscaling settings. |

### `scale`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min` | int | `1` | Minimum replicas (HPA `minReplicas`). |
| `max` | int | `3` | Maximum replicas (HPA `maxReplicas`). |
| `cpu_threshold` | int | `70` | CPU % to trigger scale-up. |
| `memory_threshold` | int | `null` | Memory % to trigger scale-up. Optional. |

---

## `infrastructure`

Named infra services included in docker-compose. Not managed in K8s (use managed services or your own manifests).

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Docker image name. e.g. `redis`, `postgres` |
| `version` | string | Image tag. e.g. `"7"`, `"16"` |

---

## `ci`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | `github` \| `gitlab` | `github` | CI platform to generate for. |
| `affected_only` | bool | `false` | Only run CI for services with changed files. Recommended for monorepos. |
| `steps` | list[string] | `[lint, test, build, push]` | Which steps to include. |
| `registry_secret` | string | `REGISTRY_TOKEN` | Secret name in CI for registry auth. |

---

## `deploy`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `target` | `kubernetes` \| `compose` \| `both` | `kubernetes` | What to generate K8s manifests for. |
| `namespace` | string | `default` | Kubernetes namespace for all resources. |
| `ingress.enabled` | bool | `false` | Generate an Ingress resource. |
| `ingress.host` | string | `null` | Hostname for the Ingress rule. |
| `ingress.tls` | bool | `false` | Add TLS config + cert-manager annotation. |
