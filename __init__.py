"""comfyui-cloud-storage - Generic cloud storage nodes for ComfyUI.

Supports any S3-compatible provider: AWS S3, Backblaze B2, Cloudflare R2,
MinIO, Wasabi, DigitalOcean Spaces, GCS (S3 interop), and custom endpoints.
"""

from typing_extensions import override
from comfy_api.latest import ComfyExtension, io


class CloudStorageExtension(ComfyExtension):
    async def on_load(self) -> None:
        try:
            import boto3  # noqa: F401
        except ImportError:
            import logging
            logging.warning(
                "comfyui-cloud-storage: boto3 not installed. "
                "Run: pip install boto3"
            )

    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        from .nodes_profile import CloudStorageProfile
        from .nodes_save import SaveImageToCloud, SaveVideoToCloud, SaveAudioToCloud
        from .nodes_load import LoadImageFromCloud, LoadModelFromCloud
        from .nodes_browse import ListBucket, GeneratePresignedURL

        return [
            CloudStorageProfile,
            SaveImageToCloud,
            SaveVideoToCloud,
            SaveAudioToCloud,
            LoadImageFromCloud,
            LoadModelFromCloud,
            ListBucket,
            GeneratePresignedURL,
        ]


async def comfy_entrypoint() -> CloudStorageExtension:
    return CloudStorageExtension()
