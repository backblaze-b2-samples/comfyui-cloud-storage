"""Load nodes - download images and models from S3-compatible storage."""

import io as io_stdlib
import os
import logging

import numpy as np
import torch
from PIL import Image, ImageOps

from comfy_api.latest import io
import comfy.utils

from .nodes_profile import S3_PROFILE_TYPE
from .profile import resolve_default_profile, validate_config
from .providers import create_s3_client

logger = logging.getLogger(__name__)


class LoadImageFromCloud(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LoadImageFromCloud",
            display_name="Load Image from Cloud",
            category="cloud_storage/load",
            description="Download an image from S3-compatible cloud storage into the pipeline.",
            search_aliases=["s3 image", "download image", "cloud image", "b2 image"],
            inputs=[
                io.String.Input(
                    "key",
                    default="",
                    tooltip="S3 object key, e.g. 'comfyui/images/photo.png'",
                ),
                io.Custom(S3_PROFILE_TYPE).Input(
                    "profile",
                    optional=True,
                    tooltip="Cloud storage profile. Uses env vars if not connected.",
                ),
            ],
            outputs=[
                io.Image.Output(),
                io.Mask.Output(),
            ],
        )

    @classmethod
    def execute(cls, key, profile=None) -> io.NodeOutput:
        from botocore.exceptions import ClientError

        config = profile or resolve_default_profile()
        validate_config(config)
        client = create_s3_client(**config)
        bucket = config["bucket"]

        # Prepend path_prefix if set
        full_key = f"{config.get('path_prefix', '')}{key}" if not key.startswith("/") else key

        try:
            response = client.get_object(Bucket=bucket, Key=full_key)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "NoSuchKey":
                raise ValueError(f"Object not found: s3://{bucket}/{full_key}") from e
            raise ValueError(f"S3 error [{code}]: {e.response['Error']['Message']}") from e

        image_data = response["Body"].read()
        img = Image.open(io_stdlib.BytesIO(image_data))
        img = ImageOps.exif_transpose(img)

        if img.mode == "I":
            img = img.point(lambda i: i * (1 / 255))

        image_rgb = img.convert("RGB")
        image_np = np.array(image_rgb).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_np)[None,]

        if "A" in img.getbands():
            mask = np.array(img.getchannel("A")).astype(np.float32) / 255.0
            mask = 1.0 - torch.from_numpy(mask)
        else:
            mask = torch.zeros(
                (image_np.shape[0], image_np.shape[1]),
                dtype=torch.float32,
            )

        return io.NodeOutput(image_tensor, mask.unsqueeze(0))

    @classmethod
    def fingerprint_inputs(cls, key, profile=None):
        """Return S3 ETag so ComfyUI re-executes when the remote object changes."""
        try:
            config = profile or resolve_default_profile()
            client = create_s3_client(**config)
            full_key = f"{config.get('path_prefix', '')}{key}"
            resp = client.head_object(Bucket=config["bucket"], Key=full_key)
            return resp.get("ETag", "")
        except Exception:
            return ""


class LoadModelFromCloud(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="LoadModelFromCloud",
            display_name="Download Model from Cloud",
            category="cloud_storage/models",
            description=(
                "Download and cache a model file from S3-compatible cloud storage. "
                "Returns the local filename for use with standard loader nodes."
            ),
            search_aliases=["s3 model", "cloud model", "download checkpoint", "b2 model"],
            inputs=[
                io.Combo.Input(
                    "model_type",
                    options=[
                        "checkpoints", "loras", "vae", "text_encoders",
                        "controlnet", "diffusion_models", "upscale_models",
                        "embeddings", "clip_vision",
                    ],
                    default="checkpoints",
                    tooltip="Which model category to save to (determines local directory).",
                ),
                io.String.Input(
                    "key",
                    default="",
                    tooltip="S3 object key, e.g. 'models/sd_xl_base_1.0.safetensors'",
                ),
                io.Boolean.Input(
                    "force_redownload",
                    default=False,
                    tooltip="Re-download even if cached locally.",
                ),
                io.Custom(S3_PROFILE_TYPE).Input("profile", optional=True),
            ],
            outputs=[
                io.String.Output(display_name="model_filename"),
            ],
        )

    @classmethod
    def execute(cls, model_type, key, force_redownload=False, profile=None) -> io.NodeOutput:
        import folder_paths
        from botocore.exceptions import ClientError

        config = profile or resolve_default_profile()
        validate_config(config)
        client = create_s3_client(**config)
        bucket = config["bucket"]
        full_key = f"{config.get('path_prefix', '')}{key}"

        # Resolve local cache path
        model_paths = folder_paths.get_folder_paths(model_type)
        if not model_paths:
            raise ValueError(f"No directory configured for model type: {model_type}")
        local_dir = model_paths[0]
        filename = os.path.basename(full_key)
        local_path = os.path.join(local_dir, filename)
        etag_path = local_path + ".s3etag"

        # Check cache
        if os.path.exists(local_path) and not force_redownload:
            try:
                remote_head = client.head_object(Bucket=bucket, Key=full_key)
                remote_etag = remote_head.get("ETag", "")
                if os.path.exists(etag_path):
                    with open(etag_path, "r") as f:
                        cached_etag = f.read().strip()
                    if cached_etag == remote_etag:
                        logger.info("Model cached: %s", local_path)
                        return io.NodeOutput(filename)
            except ClientError:
                # Can't verify, but file exists - use it
                if os.path.exists(local_path):
                    return io.NodeOutput(filename)

        # Download with progress
        try:
            head = client.head_object(Bucket=bucket, Key=full_key)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("NoSuchKey", "404"):
                raise ValueError(f"Model not found: s3://{bucket}/{full_key}") from e
            raise ValueError(f"S3 error [{code}]: {e.response['Error']['Message']}") from e

        file_size = head["ContentLength"]
        remote_etag = head.get("ETag", "")

        logger.info(
            "Downloading %s (%.2f GB) from s3://%s/%s",
            filename, file_size / (1024**3), bucket, full_key,
        )

        os.makedirs(local_dir, exist_ok=True)
        temp_path = local_path + ".download"

        pbar = comfy.utils.ProgressBar(file_size)
        downloaded = 0

        def progress_callback(bytes_amount):
            nonlocal downloaded
            downloaded += bytes_amount
            pbar.update_absolute(downloaded, file_size)

        try:
            client.download_file(
                bucket, full_key, temp_path,
                Callback=progress_callback,
            )
            os.replace(temp_path, local_path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

        # Store ETag for cache validation
        if remote_etag:
            with open(etag_path, "w") as f:
                f.write(remote_etag)

        logger.info("Model downloaded to: %s", local_path)
        return io.NodeOutput(filename)
