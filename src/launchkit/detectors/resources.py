"""Resource profiler — infers resource limits and scaling from service signals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResourceProfile:
    """Inferred resource allocation for a service."""

    profile_name: str  # human-readable label
    cpu_request: str
    cpu_limit: str
    memory_request: str
    memory_limit: str
    # Scaling hints
    scale_min: int = 1
    scale_max: int = 5
    cpu_threshold: int = 70
    memory_threshold: int | None = None


# ── Built-in profiles ────────────────────────────────────────────────────────

PROFILES: dict[str, ResourceProfile] = {
    "lightweight-api": ResourceProfile(
        profile_name="lightweight-api",
        cpu_request="50m", cpu_limit="200m",
        memory_request="64Mi", memory_limit="256Mi",
        scale_min=1, scale_max=10, cpu_threshold=65,
    ),
    "standard-api": ResourceProfile(
        profile_name="standard-api",
        cpu_request="100m", cpu_limit="500m",
        memory_request="128Mi", memory_limit="512Mi",
        scale_min=1, scale_max=5, cpu_threshold=70,
    ),
    "heavy-api": ResourceProfile(
        profile_name="heavy-api",
        cpu_request="250m", cpu_limit="1000m",
        memory_request="256Mi", memory_limit="1Gi",
        scale_min=2, scale_max=8, cpu_threshold=60,
    ),
    "worker": ResourceProfile(
        profile_name="worker",
        cpu_request="200m", cpu_limit="1000m",
        memory_request="256Mi", memory_limit="1Gi",
        scale_min=1, scale_max=5, cpu_threshold=75,
    ),
    "ml-worker": ResourceProfile(
        profile_name="ml-worker",
        cpu_request="500m", cpu_limit="2000m",
        memory_request="512Mi", memory_limit="2Gi",
        scale_min=1, scale_max=3, cpu_threshold=60,
        memory_threshold=75,
    ),
    "data-processor": ResourceProfile(
        profile_name="data-processor",
        cpu_request="250m", cpu_limit="1500m",
        memory_request="512Mi", memory_limit="2Gi",
        scale_min=1, scale_max=5, cpu_threshold=70,
        memory_threshold=80,
    ),
    "frontend": ResourceProfile(
        profile_name="frontend",
        cpu_request="50m", cpu_limit="200m",
        memory_request="64Mi", memory_limit="256Mi",
        scale_min=1, scale_max=5, cpu_threshold=80,
    ),
    # JVM-based services need more memory baseline
    "jvm-api": ResourceProfile(
        profile_name="jvm-api",
        cpu_request="200m", cpu_limit="1000m",
        memory_request="256Mi", memory_limit="1Gi",
        scale_min=1, scale_max=5, cpu_threshold=65,
    ),
    "jvm-heavy": ResourceProfile(
        profile_name="jvm-heavy",
        cpu_request="500m", cpu_limit="2000m",
        memory_request="512Mi", memory_limit="2Gi",
        scale_min=1, scale_max=3, cpu_threshold=60,
        memory_threshold=75,
    ),
    # PHP-FPM process model needs moderate memory
    "php-fpm": ResourceProfile(
        profile_name="php-fpm",
        cpu_request="100m", cpu_limit="500m",
        memory_request="128Mi", memory_limit="512Mi",
        scale_min=1, scale_max=5, cpu_threshold=70,
    ),
}


# ── Dependency signals ───────────────────────────────────────────────────────

# Heavy ML/AI libraries that need more resources
ML_SIGNALS = {
    "tensorflow", "torch", "pytorch", "transformers", "scikit-learn",
    "sklearn", "keras", "xgboost", "lightgbm", "catboost", "spacy",
    "huggingface", "onnxruntime", "jax",
}

# Data processing libraries
DATA_SIGNALS = {
    "pandas", "numpy", "scipy", "polars", "dask", "pyspark",
    "apache-beam", "prefect", "airflow", "luigi",
}

# Image/video/file processing
MEDIA_SIGNALS = {
    "pillow", "pil", "opencv-python", "ffmpeg", "imagemagick",
    "wand", "moviepy",
}

# Heavy computation indicators
HEAVY_SIGNALS = ML_SIGNALS | DATA_SIGNALS | MEDIA_SIGNALS


def infer_resource_profile(
    lang: str,
    framework: str | None,
    service_type: str,
    service_path: Path | None = None,
) -> ResourceProfile:
    """
    Infer the right resource profile for a service based on its signals.

    Decision tree:
    1. Workers with ML deps → ml-worker
    2. Workers with data deps → data-processor
    3. Workers → worker
    4. Go / Rust APIs → lightweight-api (compiled, low memory)
    5. Node frontends (Next.js, React) → frontend
    6. Java/JVM APIs → jvm-api (higher memory for JVM overhead)
    7. Python APIs with heavy deps → heavy-api
    8. PHP APIs → php-fpm
    9. Python / Node / .NET / Ruby APIs → standard-api
    10. Default → standard-api
    """
    deps = set()
    if service_path:
        deps = _scan_dependencies(service_path, lang)

    # Workers
    if service_type == "worker":
        ml_overlap = deps & ML_SIGNALS
        if ml_overlap:
            return PROFILES["ml-worker"]
        data_overlap = deps & (DATA_SIGNALS | MEDIA_SIGNALS)
        if data_overlap:
            return PROFILES["data-processor"]
        return PROFILES["worker"]

    # Frontends
    if framework in ("nextjs", "react", "vue", "svelte", "angular"):
        return PROFILES["frontend"]

    # Go and Rust APIs are lightweight (compiled, no runtime overhead)
    if lang in ("go", "rust"):
        return PROFILES["lightweight-api"]

    # Java/JVM — higher memory baseline for JVM overhead
    if lang == "java":
        heavy_overlap = deps & HEAVY_SIGNALS
        if heavy_overlap:
            return PROFILES["jvm-heavy"]
        return PROFILES["jvm-api"]

    # Python APIs — check for heavy deps
    if lang == "python":
        heavy_overlap = deps & HEAVY_SIGNALS
        if heavy_overlap:
            return PROFILES["heavy-api"]
        return PROFILES["standard-api"]

    # PHP — process-based model
    if lang == "php":
        return PROFILES["php-fpm"]

    # Node, .NET, Ruby → standard
    if lang in ("node", "dotnet", "ruby"):
        return PROFILES["standard-api"]

    return PROFILES["standard-api"]


def _scan_dependencies(service_path: Path, lang: str) -> set[str]:
    """
    Scan dependency files to extract package names.

    Reads requirements.txt / pyproject.toml / package.json / go.mod /
    pom.xml / Cargo.toml / Gemfile / composer.json / *.csproj
    and returns a set of lowercased package names.
    """
    deps: set[str] = set()

    if lang == "python":
        # requirements.txt
        req = service_path / "requirements.txt"
        if req.exists():
            try:
                for line in req.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    # "fastapi>=0.110" → "fastapi"
                    pkg = line.split(">=")[0].split("<=")[0].split("==")[0]
                    pkg = pkg.split(">")[0].split("<")[0].split("[")[0].split(";")[0]
                    deps.add(pkg.strip().lower())
            except OSError:
                pass

        # pyproject.toml (simple scan)
        pyproj = service_path / "pyproject.toml"
        if pyproj.exists():
            try:
                content = pyproj.read_text().lower()
                for signal in HEAVY_SIGNALS:
                    if signal in content:
                        deps.add(signal)
            except OSError:
                pass

    elif lang == "node":
        pkg_file = service_path / "package.json"
        if pkg_file.exists():
            try:
                import json
                data = json.loads(pkg_file.read_text())
                all_deps = {
                    **data.get("dependencies", {}),
                    **data.get("devDependencies", {}),
                }
                deps = {k.lower() for k in all_deps.keys()}
            except (OSError, ValueError):
                pass

    elif lang == "go":
        gomod = service_path / "go.mod"
        if gomod.exists():
            try:
                content = gomod.read_text().lower()
                for signal in HEAVY_SIGNALS:
                    if signal in content:
                        deps.add(signal)
            except OSError:
                pass

    elif lang == "java":
        # Scan pom.xml and build.gradle for heavy deps
        for fname in ["pom.xml", "build.gradle", "build.gradle.kts"]:
            f = service_path / fname
            if f.exists():
                try:
                    content = f.read_text().lower()
                    for signal in HEAVY_SIGNALS:
                        if signal in content:
                            deps.add(signal)
                except OSError:
                    pass

    elif lang == "rust":
        cargo = service_path / "Cargo.toml"
        if cargo.exists():
            try:
                content = cargo.read_text().lower()
                for signal in HEAVY_SIGNALS:
                    if signal in content:
                        deps.add(signal)
            except OSError:
                pass

    elif lang == "ruby":
        gemfile = service_path / "Gemfile"
        if gemfile.exists():
            try:
                content = gemfile.read_text().lower()
                for signal in HEAVY_SIGNALS:
                    if signal in content:
                        deps.add(signal)
            except OSError:
                pass

    elif lang == "php":
        composer = service_path / "composer.json"
        if composer.exists():
            try:
                import json
                data = json.loads(composer.read_text())
                all_deps = {**data.get("require", {}), **data.get("require-dev", {})}
                deps = {k.lower() for k in all_deps.keys()}
            except (OSError, ValueError):
                pass

    elif lang == "dotnet":
        for csproj in service_path.glob("*.csproj"):
            try:
                content = csproj.read_text().lower()
                for signal in HEAVY_SIGNALS:
                    if signal in content:
                        deps.add(signal)
            except OSError:
                pass

    return deps
