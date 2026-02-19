"""CloudStorageProfile node - configure once, wire to all cloud storage nodes."""

from comfy_api.latest import io

from .providers import PROVIDER_NAMES
from .profile import load_profile_names, resolve_profile, validate_config, _get_profiles_path

S3_PROFILE_TYPE = "S3_PROFILE"


class CloudStorageProfile(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        profile_names = load_profile_names()
        return io.Schema(
            node_id="CloudStorageProfile",
            display_name="Cloud Storage Profile",
            category="cloud_storage",
            description=(
                "Configure cloud storage credentials. Connect to any cloud storage node. "
                f"Profiles are stored in: {_get_profiles_path()}"
            ),
            inputs=[
                io.Combo.Input(
                    "profile",
                    options=["(env vars)", *profile_names],
                    default="(env vars)",
                    tooltip="Named profile from profiles.json, or use environment variables.",
                ),
                io.Combo.Input(
                    "provider",
                    options=["(from profile)", *PROVIDER_NAMES],
                    default="(from profile)",
                    tooltip="Override the storage provider.",
                    optional=True,
                ),
                io.String.Input(
                    "bucket",
                    default="",
                    tooltip="Override bucket name.",
                    optional=True,
                ),
                io.String.Input(
                    "path_prefix",
                    default="",
                    tooltip="Key prefix for all operations, e.g. 'comfyui/outputs/'",
                    optional=True,
                ),
            ],
            outputs=[
                io.Custom(S3_PROFILE_TYPE).Output(display_name="profile"),
            ],
        )

    @classmethod
    def execute(
        cls,
        profile="(env vars)",
        provider="(from profile)",
        bucket="",
        path_prefix="",
    ) -> io.NodeOutput:
        config = resolve_profile(profile, provider, bucket, path_prefix)
        validate_config(config)
        return io.NodeOutput(config)
