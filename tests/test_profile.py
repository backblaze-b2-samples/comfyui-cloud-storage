"""Tests for profile.py - credential resolution."""

import json
import os
import pytest
from unittest.mock import patch, mock_open


class TestProfileFromEnv:
    @patch.dict(os.environ, {
        "COMFY_S3_PROVIDER": "Backblaze B2",
        "COMFY_S3_ACCESS_KEY": "envkey",
        "COMFY_S3_SECRET_KEY": "envsecret",
        "COMFY_S3_BUCKET": "envbucket",
        "COMFY_S3_REGION": "us-west-004",
    }, clear=False)
    def test_reads_env_vars(self):
        from comfyui_cloud_storage.profile import _profile_from_env
        profile = _profile_from_env()
        assert profile["provider"] == "Backblaze B2"
        assert profile["access_key"] == "envkey"
        assert profile["secret_key"] == "envsecret"
        assert profile["bucket"] == "envbucket"
        assert profile["region"] == "us-west-004"

    @patch.dict(os.environ, {}, clear=True)
    def test_empty_when_no_env_vars(self):
        from comfyui_cloud_storage.profile import _profile_from_env
        profile = _profile_from_env()
        assert profile == {}


class TestResolveProfile:
    @patch.dict(os.environ, {
        "COMFY_S3_ACCESS_KEY": "envkey",
        "COMFY_S3_SECRET_KEY": "envsecret",
        "COMFY_S3_BUCKET": "envbucket",
    }, clear=False)
    @patch("comfyui_cloud_storage.profile._load_profiles", return_value={})
    def test_env_vars_only(self, _mock_profiles):
        from comfyui_cloud_storage.profile import resolve_profile
        config = resolve_profile("(env vars)")
        assert config["access_key"] == "envkey"
        assert config["secret_key"] == "envsecret"
        assert config["bucket"] == "envbucket"

    @patch.dict(os.environ, {
        "COMFY_S3_ACCESS_KEY": "envkey",
        "COMFY_S3_SECRET_KEY": "envsecret",
        "COMFY_S3_BUCKET": "envbucket",
    }, clear=False)
    @patch("comfyui_cloud_storage.profile._load_profiles", return_value={
        "production": {
            "provider": "Backblaze B2",
            "access_key": "profilekey",
            "secret_key": "profilesecret",
            "bucket": "profilebucket",
            "region": "eu-central-003",
        }
    })
    def test_named_profile_overlays_env(self, _mock_profiles):
        from comfyui_cloud_storage.profile import resolve_profile
        config = resolve_profile("production")
        assert config["access_key"] == "profilekey"
        assert config["bucket"] == "profilebucket"
        assert config["region"] == "eu-central-003"

    @patch.dict(os.environ, {
        "COMFY_S3_ACCESS_KEY": "envkey",
        "COMFY_S3_SECRET_KEY": "envsecret",
        "COMFY_S3_BUCKET": "envbucket",
    }, clear=False)
    @patch("comfyui_cloud_storage.profile._load_profiles", return_value={})
    def test_widget_overrides(self, _mock_profiles):
        from comfyui_cloud_storage.profile import resolve_profile
        config = resolve_profile(
            "(env vars)",
            provider_override="Backblaze B2",
            bucket_override="mybucket",
            path_prefix_override="outputs/",
        )
        assert config["provider"] == "Backblaze B2"
        assert config["bucket"] == "mybucket"
        assert config["path_prefix"] == "outputs/"
        # Credentials still from env
        assert config["access_key"] == "envkey"

    @patch.dict(os.environ, {}, clear=True)
    @patch("comfyui_cloud_storage.profile._load_profiles", return_value={})
    def test_missing_profile_warns(self, _mock_profiles):
        from comfyui_cloud_storage.profile import resolve_profile
        # Should not raise, just warn
        config = resolve_profile("nonexistent")
        assert config["access_key"] == ""

    @patch("comfyui_cloud_storage.profile._load_profiles", return_value={})
    def test_from_profile_provider_ignored(self, _mock_profiles):
        from comfyui_cloud_storage.profile import resolve_profile
        config = resolve_profile("(env vars)", provider_override="(from profile)")
        # Should not set provider to "(from profile)"
        assert config["provider"] != "(from profile)"


class TestValidateConfig:
    def test_missing_access_key_raises(self):
        from comfyui_cloud_storage.profile import validate_config
        with pytest.raises(ValueError, match="access key"):
            validate_config({"access_key": "", "secret_key": "x", "bucket": "x"})

    def test_missing_secret_key_raises(self):
        from comfyui_cloud_storage.profile import validate_config
        with pytest.raises(ValueError, match="secret key"):
            validate_config({"access_key": "x", "secret_key": "", "bucket": "x"})

    def test_missing_bucket_raises(self):
        from comfyui_cloud_storage.profile import validate_config
        with pytest.raises(ValueError, match="bucket"):
            validate_config({"access_key": "x", "secret_key": "x", "bucket": ""})

    def test_valid_config_passes(self):
        from comfyui_cloud_storage.profile import validate_config
        validate_config({"access_key": "x", "secret_key": "x", "bucket": "x"})


class TestLoadProfileNames:
    @patch("comfyui_cloud_storage.profile._load_profiles", return_value={
        "default": {}, "production": {}, "staging": {}
    })
    def test_returns_profile_names(self, _mock):
        from comfyui_cloud_storage.profile import load_profile_names
        names = load_profile_names()
        assert names == ["default", "production", "staging"]

    @patch("comfyui_cloud_storage.profile._load_profiles", return_value={})
    def test_empty_when_no_profiles(self, _mock):
        from comfyui_cloud_storage.profile import load_profile_names
        assert load_profile_names() == []
