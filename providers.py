"""
S3-compatible provider presets and client factory.

Supports: AWS S3, Backblaze B2, Cloudflare R2, MinIO, Wasabi,
DigitalOcean Spaces, GCS (S3 interop), and any custom S3 endpoint.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    endpoint_template: str  # "" means boto3 default (AWS), else "{region}" placeholders
    default_region: str = "us-east-1"
    force_path_style: bool = False


PROVIDERS: dict[str, ProviderPreset] = {
    "AWS S3": ProviderPreset(
        endpoint_template="",
        default_region="us-east-1",
    ),
    "Backblaze B2": ProviderPreset(
        endpoint_template="https://s3.{region}.backblazeb2.com",
        default_region="us-west-004",
    ),
    "Cloudflare R2": ProviderPreset(
        endpoint_template="https://{account_id}.r2.cloudflarestorage.com",
        default_region="auto",
    ),
    "MinIO": ProviderPreset(
        endpoint_template="http://localhost:9000",
        default_region="us-east-1",
        force_path_style=True,
    ),
    "Wasabi": ProviderPreset(
        endpoint_template="https://s3.{region}.wasabisys.com",
        default_region="us-east-1",
    ),
    "DigitalOcean Spaces": ProviderPreset(
        endpoint_template="https://{region}.digitaloceanspaces.com",
        default_region="nyc3",
    ),
    "GCS (S3 interop)": ProviderPreset(
        endpoint_template="https://storage.googleapis.com",
        default_region="auto",
    ),
    "Custom": ProviderPreset(
        endpoint_template="",
        default_region="",
    ),
}

PROVIDER_NAMES = list(PROVIDERS.keys())


def create_s3_client(
    provider: str = "AWS S3",
    access_key: str = "",
    secret_key: str = "",
    region: str = "",
    endpoint_url: str = "",
    account_id: str = "",
):
    """Create a boto3 S3 client configured for the given provider.

    Uses lazy import so boto3 is only loaded when actually needed.
    """
    import boto3
    from botocore.config import Config

    preset = PROVIDERS.get(provider, PROVIDERS["Custom"])
    effective_region = region or preset.default_region

    # Resolve endpoint: explicit override > preset template
    if endpoint_url:
        effective_endpoint = endpoint_url
    elif preset.endpoint_template:
        effective_endpoint = preset.endpoint_template.format(
            region=effective_region,
            account_id=account_id,
        )
    else:
        effective_endpoint = ""

    kwargs = {
        "aws_access_key_id": access_key,
        "aws_secret_access_key": secret_key,
        "region_name": effective_region,
        "config": Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if preset.force_path_style else "auto"},
            retries={"max_attempts": 3, "mode": "adaptive"},
            user_agent_extra="b2ai-comfyui",
        ),
    }
    if effective_endpoint:
        kwargs["endpoint_url"] = effective_endpoint

    return boto3.client("s3", **kwargs)
