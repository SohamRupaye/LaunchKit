"""Config loader — parses and validates launchkit.yaml into typed models."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


class Lang(str, Enum):
    PYTHON = "python"
    NODE = "node"
    GO = "go"
    JAVA = "java"
    RUST = "rust"
    RUBY = "ruby"
    PHP = "php"
    DOTNET = "dotnet"


class ServiceType(str, Enum):
    WEB = "web"
    WORKER = "worker"


class CIProvider(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class DeployTarget(str, Enum):
    KUBERNETES = "kubernetes"
    COMPOSE = "compose"
    BOTH = "both"


class ScaleConfig(BaseModel):
    min: int = 1
    max: int = 3
    cpu_threshold: int = 70
    memory_threshold: int | None = None


class ResourceConfig(BaseModel):
    """Resource requests and limits for K8s deployments (inferred or manual)."""

    profile: str | None = None
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"


class ServiceConfig(BaseModel):
    lang: Lang
    framework: str | None = None
    port: int | None = None
    type: ServiceType = ServiceType.WEB
    healthcheck: str | None = None
    env_file: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    scale: ScaleConfig = Field(default_factory=ScaleConfig)
    resources: ResourceConfig = Field(default_factory=ResourceConfig)

    @model_validator(mode="after")
    def worker_has_no_port(self) -> ServiceConfig:
        if self.type == ServiceType.WORKER and self.port is not None:
            raise ValueError("Worker services should not define a port")
        return self


class InfrastructureItem(BaseModel):
    type: str
    version: str = "latest"


class IngressConfig(BaseModel):
    enabled: bool = False
    host: str | None = None
    tls: bool = False


class NginxConfig(BaseModel):
    """Nginx reverse proxy configuration."""

    enabled: bool = True
    rate_limit: str = "10r/s"
    client_max_body: str = "10m"
    gzip: bool = True


class EnvironmentOverride(BaseModel):
    """Per-environment overrides (staging, production, etc.)."""

    namespace: str | None = None
    domain: str | None = None
    tls: bool | None = None
    scale: ScaleConfig | None = None
    resources: ResourceConfig | None = None
    replicas: int | None = None


class DeployConfig(BaseModel):
    target: DeployTarget = DeployTarget.KUBERNETES
    namespace: str = "default"
    ingress: IngressConfig = Field(default_factory=IngressConfig)
    nginx: NginxConfig = Field(default_factory=NginxConfig)


class CIConfig(BaseModel):
    provider: CIProvider = CIProvider.GITHUB
    affected_only: bool = False
    branches: list[str] = Field(default_factory=lambda: ["main"])
    steps: list[str] = Field(default_factory=lambda: ["lint", "test", "build", "push"])
    registry_secret: str = "REGISTRY_TOKEN"


class ProjectConfig(BaseModel):
    name: str
    registry: str


class LaunchKitConfig(BaseModel):
    version: str
    project: ProjectConfig
    services: dict[str, ServiceConfig]
    infrastructure: dict[str, InfrastructureItem] = Field(default_factory=dict)
    environments: dict[str, EnvironmentOverride] = Field(default_factory=dict)
    ci: CIConfig = Field(default_factory=CIConfig)
    deploy: DeployConfig = Field(default_factory=DeployConfig)


def load_and_validate(config_path: str = "launchkit.yaml") -> LaunchKitConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"{config_path} not found. Run `launchkit init` to generate one."
        )
    raw: dict[str, Any] = yaml.safe_load(path.read_text())
    return LaunchKitConfig.model_validate(raw)


def apply_environment(cfg: LaunchKitConfig, env_name: str) -> LaunchKitConfig:
    """
    Apply an environment override to the config, returning a new config.

    Merges the environment's overrides into the base config for generation.
    """
    if env_name not in cfg.environments:
        raise ValueError(
            f"Environment '{env_name}' not found. "
            f"Available: {', '.join(cfg.environments.keys()) or 'none defined'}"
        )

    override = cfg.environments[env_name]

    # Deep copy via model export/import
    data = cfg.model_dump()

    # Apply environment-level overrides
    if override.namespace:
        data["deploy"]["namespace"] = override.namespace
    if override.domain:
        data["deploy"]["ingress"]["host"] = override.domain
        data["deploy"]["ingress"]["enabled"] = True
    if override.tls is not None:
        data["deploy"]["ingress"]["tls"] = override.tls

    # Apply per-service overrides
    for svc_name in data["services"]:
        if override.scale:
            for k, v in override.scale.model_dump(exclude_none=True).items():
                data["services"][svc_name]["scale"][k] = v
        if override.resources:
            for k, v in override.resources.model_dump(exclude_none=True).items():
                data["services"][svc_name]["resources"][k] = v
        if override.replicas is not None:
            data["services"][svc_name]["scale"]["min"] = override.replicas

    return LaunchKitConfig.model_validate(data)
