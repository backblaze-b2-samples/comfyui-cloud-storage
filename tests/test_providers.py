"""Tests for providers.py - provider presets and S3 client factory."""

import sys
import pytest
from unittest.mock import patch, MagicMock


class TestProviderPresets:
    def test_all_providers_have_required_fields(self):
        from comfyui_cloud_storage.providers import PROVIDERS
        for name, preset in PROVIDERS.items():
            assert hasattr(preset, "endpoint_template"), f"{name} missing endpoint_template"
            assert hasattr(preset, "default_region"), f"{name} missing default_region"
            assert hasattr(preset, "force_path_style"), f"{name} missing force_path_style"

    def test_provider_names_matches_keys(self):
        from comfyui_cloud_storage.providers import PROVIDERS, PROVIDER_NAMES
        assert PROVIDER_NAMES == list(PROVIDERS.keys())

    def test_b2_endpoint_template(self):
        from comfyui_cloud_storage.providers import PROVIDERS
        b2 = PROVIDERS["Backblaze B2"]
        endpoint = b2.endpoint_template.format(region="us-west-004", account_id="")
        assert endpoint == "https://s3.us-west-004.backblazeb2.com"

    def test_r2_endpoint_template(self):
        from comfyui_cloud_storage.providers import PROVIDERS
        r2 = PROVIDERS["Cloudflare R2"]
        endpoint = r2.endpoint_template.format(region="auto", account_id="abc123")
        assert endpoint == "https://abc123.r2.cloudflarestorage.com"

    def test_aws_has_empty_endpoint(self):
        from comfyui_cloud_storage.providers import PROVIDERS
        assert PROVIDERS["AWS S3"].endpoint_template == ""

    def test_minio_uses_path_style(self):
        from comfyui_cloud_storage.providers import PROVIDERS
        assert PROVIDERS["MinIO"].force_path_style is True

    def test_non_minio_uses_auto_style(self):
        from comfyui_cloud_storage.providers import PROVIDERS
        for name, preset in PROVIDERS.items():
            if name != "MinIO":
                assert preset.force_path_style is False, f"{name} should not use path style"


class TestCreateS3Client:
    def _call_with_mock_boto3(self, **kwargs):
        """Call create_s3_client with a mocked boto3 and return the mock + call args."""
        mock_boto3 = MagicMock()
        with patch.dict(sys.modules, {"boto3": mock_boto3}):
            # Need to re-import to pick up the mock
            from comfyui_cloud_storage.providers import create_s3_client
            create_s3_client(**kwargs)
        return mock_boto3

    def test_aws_no_endpoint_url(self):
        mock_boto3 = self._call_with_mock_boto3(
            provider="AWS S3", access_key="AKID", secret_key="SECRET",
        )
        call_kwargs = mock_boto3.client.call_args
        assert "endpoint_url" not in call_kwargs.kwargs

    def test_b2_sets_endpoint(self):
        mock_boto3 = self._call_with_mock_boto3(
            provider="Backblaze B2", access_key="AKID", secret_key="SECRET",
            region="eu-central-003",
        )
        call_kwargs = mock_boto3.client.call_args
        assert call_kwargs.kwargs["endpoint_url"] == "https://s3.eu-central-003.backblazeb2.com"

    def test_custom_endpoint_overrides_preset(self):
        mock_boto3 = self._call_with_mock_boto3(
            provider="Backblaze B2", access_key="AKID", secret_key="SECRET",
            endpoint_url="https://custom.example.com",
        )
        call_kwargs = mock_boto3.client.call_args
        assert call_kwargs.kwargs["endpoint_url"] == "https://custom.example.com"

    def test_credentials_passed_through(self):
        mock_boto3 = self._call_with_mock_boto3(
            provider="AWS S3", access_key="mykey", secret_key="mysecret",
            region="us-west-2",
        )
        call_kwargs = mock_boto3.client.call_args
        assert call_kwargs.kwargs["aws_access_key_id"] == "mykey"
        assert call_kwargs.kwargs["aws_secret_access_key"] == "mysecret"
        assert call_kwargs.kwargs["region_name"] == "us-west-2"

    def test_unknown_provider_uses_custom(self):
        mock_boto3 = self._call_with_mock_boto3(
            provider="SomeUnknown", access_key="AKID", secret_key="SECRET",
            endpoint_url="https://unknown.example.com",
        )
        call_kwargs = mock_boto3.client.call_args
        assert call_kwargs.kwargs["endpoint_url"] == "https://unknown.example.com"

    def test_user_agent_set(self):
        from botocore.config import Config
        mock_boto3 = self._call_with_mock_boto3(
            provider="Backblaze B2", access_key="AKID", secret_key="SECRET",
        )
        config = mock_boto3.client.call_args.kwargs["config"]
        assert isinstance(config, Config)
        assert config.user_agent_extra == "b2ai-comfyui"
