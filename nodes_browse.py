"""Browse nodes - list bucket contents and generate presigned URLs."""

import logging

from comfy_api.latest import io

from .nodes_profile import S3_PROFILE_TYPE
from .profile import resolve_default_profile, validate_config
from .providers import create_s3_client

logger = logging.getLogger(__name__)


class ListBucket(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="ListBucketContents",
            display_name="List Bucket Contents",
            category="cloud_storage/browse",
            description="List files in an S3-compatible bucket.",
            search_aliases=["s3 list", "bucket browse", "cloud files"],
            inputs=[
                io.String.Input(
                    "prefix",
                    default="",
                    tooltip="Filter results to keys starting with this prefix.",
                ),
                io.Int.Input(
                    "max_results",
                    default=100,
                    min=1,
                    max=1000,
                ),
                io.Custom(S3_PROFILE_TYPE).Input("profile", optional=True),
            ],
            outputs=[
                io.String.Output(display_name="file_list"),
            ],
            not_idempotent=True,
        )

    @classmethod
    def execute(cls, prefix="", max_results=100, profile=None) -> io.NodeOutput:
        from botocore.exceptions import ClientError

        config = profile or resolve_default_profile()
        validate_config(config)
        client = create_s3_client(**config)
        bucket = config["bucket"]

        full_prefix = f"{config.get('path_prefix', '')}{prefix}"

        try:
            paginator = client.get_paginator("list_objects_v2")
            keys = []
            for page in paginator.paginate(
                Bucket=bucket,
                Prefix=full_prefix,
                PaginationConfig={"MaxItems": max_results},
            ):
                for obj in page.get("Contents", []):
                    size_mb = obj["Size"] / (1024 * 1024)
                    keys.append(f"{obj['Key']}  ({size_mb:.1f} MB)")
        except ClientError as e:
            code = e.response["Error"]["Code"]
            raise ValueError(f"S3 error [{code}]: {e.response['Error']['Message']}") from e

        return io.NodeOutput("\n".join(keys))


class GeneratePresignedURL(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="GeneratePresignedURL",
            display_name="Generate Sharing URL",
            category="cloud_storage/browse",
            description="Generate a time-limited presigned URL for sharing a cloud storage file.",
            search_aliases=["s3 url", "share link", "presigned"],
            inputs=[
                io.String.Input(
                    "key",
                    default="",
                    tooltip="S3 object key to generate a URL for.",
                ),
                io.Int.Input(
                    "expires_hours",
                    default=24,
                    min=1,
                    max=168,
                    tooltip="URL expiration time in hours (max 7 days).",
                ),
                io.Custom(S3_PROFILE_TYPE).Input("profile", optional=True),
            ],
            outputs=[
                io.String.Output(display_name="url"),
            ],
            not_idempotent=True,
        )

    @classmethod
    def execute(cls, key, expires_hours=24, profile=None) -> io.NodeOutput:
        from botocore.exceptions import ClientError

        config = profile or resolve_default_profile()
        validate_config(config)
        client = create_s3_client(**config)
        bucket = config["bucket"]

        full_key = f"{config.get('path_prefix', '')}{key}"

        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": full_key},
                ExpiresIn=expires_hours * 3600,
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            raise ValueError(f"S3 error [{code}]: {e.response['Error']['Message']}") from e

        return io.NodeOutput(url)
