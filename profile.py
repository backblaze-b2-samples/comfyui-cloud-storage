"""
Cloud storage profile resolution.

Credentials are resolved in layers:
1. Environment variables (COMFY_S3_*)
2. Named profiles from JSON file in ComfyUI's system user directory
3. Per-node widget overrides (bucket, prefix only - never keys)
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

ENV_PREFIX = "COMFY_S3_"

# Map of env var suffix -> profile dict key
ENV_KEYS = {
    "PROVIDER": "provider",
    "ACCESS_KEY": "access_key",
    "SECRET_KEY": "secret_key",
    "REGION": "region",
    "BUCKET": "bucket",
    "ENDPOINT_URL": "endpoint_url",
    "ACCOUNT_ID": "account_id",
    "PATH_PREFIX": "path_prefix",
}


def _get_profiles_path() -> str:
    """Get path to the profiles JSON file in ComfyUI's system user directory."""
    try:
        import folder_paths
        sys_dir = folder_paths.get_system_user_directory("cloud_storage")
        return os.path.join(sys_dir, "profiles.json")
    except (ImportError, Exception):
        # Fallback for testing outside ComfyUI
        return os.path.join(os.path.expanduser("~"), ".comfyui-cloud-storage", "profiles.json")


def _load_profiles() -> dict:
    """Load named profiles from the JSON file."""
    path = _get_profiles_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data.get("profiles", {})
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load cloud storage profiles from %s: %s", path, e)
        return {}


def load_profile_names() -> list[str]:
    """Return list of available named profile names."""
    return list(_load_profiles().keys())


def _profile_from_env() -> dict:
    """Build a profile dict from environment variables."""
    profile = {}
    for env_suffix, key in ENV_KEYS.items():
        val = os.environ.get(f"{ENV_PREFIX}{env_suffix}", "")
        if val:
            profile[key] = val
    return profile


def resolve_profile(
    profile_name: str = "(env vars)",
    provider_override: str = "",
    bucket_override: str = "",
    path_prefix_override: str = "",
) -> dict:
    """Resolve a complete profile config dict.

    Layers: env vars -> named profile -> widget overrides.

    Returns dict with keys:
        provider, access_key, secret_key, region, bucket,
        endpoint_url, account_id, path_prefix
    """
    # Start with env vars
    config = {
        "provider": "AWS S3",
        "access_key": "",
        "secret_key": "",
        "region": "",
        "bucket": "",
        "endpoint_url": "",
        "account_id": "",
        "path_prefix": "",
    }
    config.update({k: v for k, v in _profile_from_env().items() if v})

    # Overlay named profile
    if profile_name and profile_name != "(env vars)":
        profiles = _load_profiles()
        named = profiles.get(profile_name, {})
        if not named:
            logger.warning("Cloud storage profile '%s' not found", profile_name)
        else:
            config.update({k: v for k, v in named.items() if v})

    # Overlay per-node widget overrides (never override credentials this way)
    if provider_override and provider_override != "(from profile)":
        config["provider"] = provider_override
    if bucket_override:
        config["bucket"] = bucket_override
    if path_prefix_override:
        config["path_prefix"] = path_prefix_override

    return config


def resolve_default_profile() -> dict:
    """Resolve the default profile (env vars only, no named profile)."""
    return resolve_profile("(env vars)")


def validate_config(config: dict) -> None:
    """Raise ValueError with a clear message if required fields are missing."""
    if not config.get("access_key"):
        raise ValueError(
            "Cloud storage access key not configured. "
            "Set COMFY_S3_ACCESS_KEY env var, create a profile in "
            f"{_get_profiles_path()}, or connect a CloudStorageProfile node."
        )
    if not config.get("secret_key"):
        raise ValueError(
            "Cloud storage secret key not configured. "
            "Set COMFY_S3_SECRET_KEY env var or configure a profile."
        )
    if not config.get("bucket"):
        raise ValueError(
            "Cloud storage bucket not configured. "
            "Set COMFY_S3_BUCKET env var or configure a profile."
        )
