"""docker-compose.yml generator."""

from __future__ import annotations

import yaml

from launchkit.core.config import LaunchKitConfig, ServiceType


def generate_compose(cfg: LaunchKitConfig) -> str:
    """Generate a docker-compose.yml from LaunchKit config."""
    registry = cfg.project.registry
    project_name = cfg.project.name

    compose: dict = {
        "services": {},
    }

    volumes: dict = {}

    # ── Application services ─────────────────────────────────────────────
    multi = len(cfg.services) > 1

    for name, service in cfg.services.items():
        svc_def: dict = {}

        # Build context
        if multi:
            svc_def["build"] = {
                "context": f"./services/{name}",
                "dockerfile": "Dockerfile",
            }
        else:
            svc_def["build"] = {
                "context": ".",
                "dockerfile": "Dockerfile",
            }

        svc_def["image"] = f"{registry}/{name}:latest"
        svc_def["container_name"] = f"{project_name}-{name}"

        # Ports (web services only)
        if service.type == ServiceType.WEB and service.port:
            svc_def["ports"] = [f"{service.port}:{service.port}"]

        # Environment file
        if service.env_file:
            svc_def["env_file"] = [service.env_file]

        # Dependencies
        deps = list(service.depends_on)
        if deps:
            svc_def["depends_on"] = deps

        # Healthcheck
        if service.healthcheck and service.port:
            svc_def["healthcheck"] = {
                "test": ["CMD", "curl", "-f", f"http://localhost:{service.port}{service.healthcheck}"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
                "start_period": "10s",
            }

        # Restart policy
        svc_def["restart"] = "unless-stopped"

        # Production logging limits
        svc_def["logging"] = {
            "driver": "json-file",
            "options": {
                "max-size": "10m",
                "max-file": "3"
            }
        }

        compose["services"][name] = svc_def

    # ── Infrastructure services ──────────────────────────────────────────
    for name, infra in cfg.infrastructure.items():
        infra_type = infra.type
        version = infra.version

        infra_def: dict = {
            "image": f"{infra_type}:{version}",
            "container_name": f"{project_name}-{name}",
            "restart": "unless-stopped",
            "logging": {
                "driver": "json-file",
                "options": {
                    "max-size": "10m",
                    "max-file": "3"
                }
            }
        }

        # Default ports for common infrastructure
        default_ports: dict[str, str] = {
            "redis": "6379:6379",
            "postgres": "5432:5432",
            "mysql": "3306:3306",
            "mongodb": "27017:27017",
            "rabbitmq": "5672:5672",
            "elasticsearch": "9200:9200",
        }

        if infra_type in default_ports:
            infra_def["ports"] = [default_ports[infra_type]]

        # Volumes for stateful services
        stateful = {"postgres", "mysql", "mongodb", "elasticsearch"}
        if infra_type in stateful:
            vol_name = f"{name}-data"
            infra_def["volumes"] = [f"{vol_name}:/data"]
            volumes[vol_name] = {"driver": "local"}

        # Default environment for databases
        if infra_type == "postgres":
            infra_def["environment"] = {
                "POSTGRES_USER": project_name,
                "POSTGRES_PASSWORD": "changeme",
                "POSTGRES_DB": project_name,
            }
            infra_def["volumes"] = [f"{name}-data:/var/lib/postgresql/data"]
        elif infra_type == "mysql":
            infra_def["environment"] = {
                "MYSQL_ROOT_PASSWORD": "changeme",
                "MYSQL_DATABASE": project_name,
            }
            infra_def["volumes"] = [f"{name}-data:/var/lib/mysql"]

        compose["services"][name] = infra_def

    # ── Nginx reverse proxy ──────────────────────────────────────────────
    if cfg.deploy.nginx.enabled:
        web_services = [
            n for n, s in cfg.services.items()
            if s.type == ServiceType.WEB and s.port
        ]
        if web_services:
            nginx_def: dict = {
                "image": "nginx:1.27-alpine",
                "container_name": f"{project_name}-nginx",
                "ports": ["80:80", "443:443"],
                "volumes": ["./nginx/nginx.conf:/etc/nginx/nginx.conf:ro"],
                "depends_on": web_services,
                "restart": "unless-stopped",
                "logging": {
                    "driver": "json-file",
                    "options": {
                        "max-size": "10m",
                        "max-file": "3"
                    }
                },
                "healthcheck": {
                    "test": ["CMD", "curl", "-f", "http://localhost/nginx-health"],
                    "interval": "30s",
                    "timeout": "5s",
                    "retries": 3,
                },
            }
            compose["services"]["nginx"] = nginx_def

    # ── Volumes ──────────────────────────────────────────────────────────
    if volumes:
        compose["volumes"] = volumes

    header = (
        "# Generated by LaunchKit — https://github.com/SohamRupaye/launchkit\n"
        "# Do not edit manually — run `launchkit generate --only compose` to regenerate\n\n"
    )
    return header + yaml.dump(compose, default_flow_style=False, sort_keys=False)

