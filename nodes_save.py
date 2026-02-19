"""Save nodes - upload generated images, video, and audio to S3-compatible storage."""

import io as io_stdlib
import json
import logging

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from comfy_api.latest import io
from comfy.cli_args import args

from .nodes_profile import S3_PROFILE_TYPE
from .profile import resolve_default_profile, validate_config
from .providers import create_s3_client

logger = logging.getLogger(__name__)

MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
}


def _tensor_to_image_bytes(
    image_tensor,
    fmt="png",
    quality=95,
    prompt=None,
    extra_pnginfo=None,
) -> bytes:
    """Convert a single image tensor to bytes in the specified format."""
    i = 255.0 * image_tensor.cpu().numpy()
    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

    buf = io_stdlib.BytesIO()
    save_kwargs = {}

    if fmt == "png":
        metadata = None
        if not args.disable_metadata:
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for k in extra_pnginfo:
                    metadata.add_text(k, json.dumps(extra_pnginfo[k]))
        save_kwargs["pnginfo"] = metadata
        save_kwargs["compress_level"] = 4
        img.save(buf, format="PNG", **save_kwargs)
    elif fmt == "jpg":
        img.save(buf, format="JPEG", quality=quality)
    elif fmt == "webp":
        img.save(buf, format="WEBP", quality=quality)

    return buf.getvalue()


def _build_key(config: dict, prefix: str, filename: str, batch_idx: int, ext: str) -> str:
    """Build the full S3 object key."""
    base_prefix = config.get("path_prefix", "")
    name = filename.replace("%batch_num%", str(batch_idx))
    return f"{base_prefix}{prefix}{name}.{ext}"


def _s3_error_message(e) -> str:
    """Extract a user-friendly message from a botocore ClientError."""
    from botocore.exceptions import ClientError
    if isinstance(e, ClientError):
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        if code == "NoSuchBucket":
            return f"Bucket not found: {msg}"
        if code in ("AccessDenied", "403"):
            return f"Access denied. Check credentials and bucket policy. ({msg})"
        if code == "InvalidAccessKeyId":
            return f"Invalid access key. ({msg})"
        return f"S3 error [{code}]: {msg}"
    return str(e)


class SaveImageToCloud(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SaveImageToCloud",
            display_name="Save Image to Cloud",
            category="cloud_storage/save",
            description="Upload images to S3-compatible cloud storage (B2, S3, R2, MinIO, etc.).",
            search_aliases=["upload image", "s3 save", "cloud save", "b2 save"],
            inputs=[
                io.Image.Input("images", tooltip="The images to upload."),
                io.String.Input(
                    "key_prefix",
                    default="comfyui/images/",
                    tooltip="S3 key prefix (folder path in bucket).",
                ),
                io.String.Input(
                    "filename",
                    default="ComfyUI_%batch_num%",
                    tooltip="Filename template. %batch_num% replaced with batch index.",
                ),
                io.Combo.Input("format", options=["png", "jpg", "webp"], default="png"),
                io.Int.Input(
                    "quality",
                    default=95,
                    min=1,
                    max=100,
                    tooltip="JPEG/WebP quality (ignored for PNG).",
                ),
                io.Custom(S3_PROFILE_TYPE).Input(
                    "profile",
                    optional=True,
                    tooltip="Cloud storage profile. Uses env vars if not connected.",
                ),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def execute(
        cls,
        images,
        key_prefix="comfyui/images/",
        filename="ComfyUI_%batch_num%",
        format="png",
        quality=95,
        profile=None,
    ) -> io.NodeOutput:
        from botocore.exceptions import ClientError

        config = profile or resolve_default_profile()
        validate_config(config)
        client = create_s3_client(**config)
        bucket = config["bucket"]

        uploaded = []
        for batch_idx, image_tensor in enumerate(images):
            img_bytes = _tensor_to_image_bytes(
                image_tensor,
                fmt=format,
                quality=quality,
                prompt=cls.hidden.prompt,
                extra_pnginfo=cls.hidden.extra_pnginfo,
            )
            key = _build_key(config, key_prefix, filename, batch_idx, format)
            content_type = MIME_TYPES.get(format, "application/octet-stream")

            try:
                client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=img_bytes,
                    ContentType=content_type,
                )
            except ClientError as e:
                raise ValueError(_s3_error_message(e)) from e

            uploaded.append(f"s3://{bucket}/{key}")
            logger.info("Uploaded %s (%d bytes)", key, len(img_bytes))

        return io.NodeOutput(ui={"text": uploaded})


class SaveVideoToCloud(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        from comfy_api.latest import Types
        return io.Schema(
            node_id="SaveVideoToCloud",
            display_name="Save Video to Cloud",
            category="cloud_storage/save",
            description="Upload video to S3-compatible cloud storage.",
            search_aliases=["upload video", "s3 video", "cloud video"],
            inputs=[
                io.Video.Input("video", tooltip="The video to upload."),
                io.String.Input("key_prefix", default="comfyui/videos/"),
                io.String.Input("filename", default="ComfyUI_video"),
                io.Combo.Input("format", options=Types.VideoContainer.as_input(), default="auto"),
                io.Combo.Input("codec", options=Types.VideoCodec.as_input(), default="auto"),
                io.Custom(S3_PROFILE_TYPE).Input("profile", optional=True),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, video, key_prefix, filename, format, codec, profile=None) -> io.NodeOutput:
        from botocore.exceptions import ClientError
        from comfy_api.latest import Types

        config = profile or resolve_default_profile()
        validate_config(config)
        client = create_s3_client(**config)
        bucket = config["bucket"]

        buf = io_stdlib.BytesIO()
        saved_metadata = None
        if not args.disable_metadata:
            metadata = {}
            if cls.hidden.extra_pnginfo is not None:
                metadata.update(cls.hidden.extra_pnginfo)
            if cls.hidden.prompt is not None:
                metadata["prompt"] = cls.hidden.prompt
            if metadata:
                saved_metadata = metadata

        video.save_to(
            buf,
            format=Types.VideoContainer(format),
            codec=codec,
            metadata=saved_metadata,
        )
        buf.seek(0)

        ext = Types.VideoContainer.get_extension(format)
        base_prefix = config.get("path_prefix", "")
        key = f"{base_prefix}{key_prefix}{filename}.{ext}"

        try:
            client.upload_fileobj(buf, bucket, key)
        except ClientError as e:
            raise ValueError(_s3_error_message(e)) from e

        logger.info("Uploaded video %s", key)
        return io.NodeOutput(ui={"text": [f"s3://{bucket}/{key}"]})


class SaveAudioToCloud(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="SaveAudioToCloud",
            display_name="Save Audio to Cloud",
            category="cloud_storage/save",
            description="Upload audio to S3-compatible cloud storage.",
            search_aliases=["upload audio", "s3 audio", "cloud audio"],
            inputs=[
                io.Audio.Input("audio", tooltip="The audio to upload."),
                io.String.Input("key_prefix", default="comfyui/audio/"),
                io.String.Input("filename", default="ComfyUI_audio"),
                io.Combo.Input("format", options=["flac", "mp3", "wav"], default="flac"),
                io.Custom(S3_PROFILE_TYPE).Input("profile", optional=True),
            ],
            hidden=[io.Hidden.prompt, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, audio, key_prefix, filename, format, profile=None) -> io.NodeOutput:
        from botocore.exceptions import ClientError
        import torchaudio

        config = profile or resolve_default_profile()
        validate_config(config)
        client = create_s3_client(**config)
        bucket = config["bucket"]

        buf = io_stdlib.BytesIO()
        # audio is a dict with "waveform" and "sample_rate" keys
        waveform = audio["waveform"].squeeze(0)
        sample_rate = audio["sample_rate"]
        torchaudio.save(buf, waveform, sample_rate, format=format)
        buf.seek(0)

        mime_types = {"flac": "audio/flac", "mp3": "audio/mpeg", "wav": "audio/wav"}
        base_prefix = config.get("path_prefix", "")
        key = f"{base_prefix}{key_prefix}{filename}.{format}"

        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=buf.getvalue(),
                ContentType=mime_types.get(format, "application/octet-stream"),
            )
        except ClientError as e:
            raise ValueError(_s3_error_message(e)) from e

        logger.info("Uploaded audio %s", key)
        return io.NodeOutput(ui={"text": [f"s3://{bucket}/{key}"]})
