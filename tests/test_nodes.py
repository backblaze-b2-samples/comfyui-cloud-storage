"""Tests for node logic - save, load, browse."""

import io
import os
import pytest
import numpy as np
import torch
from unittest.mock import patch, MagicMock
from PIL import Image


def _make_image_tensor(width=64, height=64, batch=1):
    """Create a dummy image tensor matching ComfyUI format: (B, H, W, 3) float32 [0,1]."""
    return torch.rand(batch, height, width, 3, dtype=torch.float32)


class TestTensorToImageBytes:
    def test_png_output(self):
        from comfyui_cloud_storage.nodes_save import _tensor_to_image_bytes
        tensor = _make_image_tensor()[0]  # single image
        with patch("comfyui_cloud_storage.nodes_save.args") as mock_args:
            mock_args.disable_metadata = True
            data = _tensor_to_image_bytes(tensor, fmt="png")
        assert data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes

    def test_jpg_output(self):
        from comfyui_cloud_storage.nodes_save import _tensor_to_image_bytes
        tensor = _make_image_tensor()[0]
        with patch("comfyui_cloud_storage.nodes_save.args") as mock_args:
            mock_args.disable_metadata = True
            data = _tensor_to_image_bytes(tensor, fmt="jpg", quality=80)
        assert data[:2] == b"\xff\xd8"  # JPEG magic bytes

    def test_webp_output(self):
        from comfyui_cloud_storage.nodes_save import _tensor_to_image_bytes
        tensor = _make_image_tensor()[0]
        with patch("comfyui_cloud_storage.nodes_save.args") as mock_args:
            mock_args.disable_metadata = True
            data = _tensor_to_image_bytes(tensor, fmt="webp")
        assert data[:4] == b"RIFF"  # WebP magic bytes


class TestBuildKey:
    def test_basic_key(self):
        from comfyui_cloud_storage.nodes_save import _build_key
        config = {"path_prefix": ""}
        key = _build_key(config, "images/", "test_%batch_num%", 0, "png")
        assert key == "images/test_0.png"

    def test_with_path_prefix(self):
        from comfyui_cloud_storage.nodes_save import _build_key
        config = {"path_prefix": "myproject/"}
        key = _build_key(config, "images/", "test_%batch_num%", 2, "jpg")
        assert key == "myproject/images/test_2.jpg"

    def test_batch_num_substitution(self):
        from comfyui_cloud_storage.nodes_save import _build_key
        config = {"path_prefix": ""}
        key = _build_key(config, "", "img_%batch_num%_%batch_num%", 5, "png")
        assert key == "img_5_5.png"


class TestS3ErrorMessage:
    def test_no_such_bucket(self):
        from comfyui_cloud_storage.nodes_save import _s3_error_message
        from botocore.exceptions import ClientError
        err = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "mybucket"}},
            "PutObject",
        )
        msg = _s3_error_message(err)
        assert "Bucket not found" in msg

    def test_access_denied(self):
        from comfyui_cloud_storage.nodes_save import _s3_error_message
        from botocore.exceptions import ClientError
        err = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "PutObject",
        )
        msg = _s3_error_message(err)
        assert "Access denied" in msg

    def test_generic_error(self):
        from comfyui_cloud_storage.nodes_save import _s3_error_message
        from botocore.exceptions import ClientError
        err = ClientError(
            {"Error": {"Code": "InternalError", "Message": "oops"}},
            "PutObject",
        )
        msg = _s3_error_message(err)
        assert "InternalError" in msg
        assert "oops" in msg

    def test_non_client_error(self):
        from comfyui_cloud_storage.nodes_save import _s3_error_message
        msg = _s3_error_message(RuntimeError("something"))
        assert "something" in msg
