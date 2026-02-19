"""Test configuration - mock ComfyUI imports for standalone testing."""

import sys
import importlib
from pathlib import Path
from unittest.mock import MagicMock
from types import ModuleType


def _setup_comfy_mocks():
    """Set up minimal ComfyUI mocks for unit testing outside ComfyUI."""
    if "comfy_api" in sys.modules:
        return

    # Mock comfy_api.latest.io
    mock_io = MagicMock()
    mock_io.ComfyNode = type("ComfyNode", (), {
        "define_schema": classmethod(lambda cls: None),
        "execute": classmethod(lambda cls, **kw: None),
        "hidden": MagicMock(),
    })
    mock_io.Schema = MagicMock
    mock_io.NodeOutput = lambda *args, **kwargs: {"result": args, "ui": kwargs.get("ui")}
    mock_io.Image = MagicMock()
    mock_io.Video = MagicMock()
    mock_io.Audio = MagicMock()
    mock_io.Mask = MagicMock()
    mock_io.String = MagicMock()
    mock_io.Int = MagicMock()
    mock_io.Float = MagicMock()
    mock_io.Boolean = MagicMock()
    mock_io.Combo = MagicMock()
    mock_io.Custom = MagicMock(return_value=MagicMock())
    mock_io.Hidden = MagicMock()
    mock_io.FolderType = MagicMock()

    mock_latest = MagicMock()
    mock_latest.io = mock_io
    mock_latest.ComfyExtension = type("ComfyExtension", (), {})
    mock_latest.ui = MagicMock()
    mock_latest.Input = MagicMock()
    mock_latest.Types = MagicMock()

    sys.modules["comfy_api"] = MagicMock(latest=mock_latest)
    sys.modules["comfy_api.latest"] = mock_latest

    # Mock comfy core
    mock_args = MagicMock()
    mock_args.disable_metadata = False
    mock_cli_args = MagicMock(args=mock_args)

    mock_utils = MagicMock()
    mock_utils.ProgressBar = MagicMock()

    sys.modules["comfy"] = MagicMock(utils=mock_utils, cli_args=mock_cli_args)
    sys.modules["comfy.utils"] = mock_utils
    sys.modules["comfy.cli_args"] = mock_cli_args

    # Mock folder_paths
    mock_fp = MagicMock()
    mock_fp.get_system_user_directory.return_value = "/tmp/comfyui-test/__cloud_storage"
    mock_fp.get_folder_paths.return_value = ["/tmp/comfyui-test-models"]
    sys.modules["folder_paths"] = mock_fp


# Set up mocks before any package imports
_setup_comfy_mocks()

# Register the package under an importable name (directory has hyphens)
pkg_root = Path(__file__).parent.parent
sys.path.insert(0, str(pkg_root.parent))  # add oss/ to path

# Create a properly named alias module
_pkg = importlib.import_module(pkg_root.name.replace("-", "_"), package=None) if pkg_root.name.replace("-", "_") in sys.modules else None
if _pkg is None:
    # Load the package from the hyphenated directory via importlib
    spec = importlib.util.spec_from_file_location(
        "comfyui_cloud_storage",
        str(pkg_root / "__init__.py"),
        submodule_search_locations=[str(pkg_root)],
    )
    _pkg = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_cloud_storage"] = _pkg
    spec.loader.exec_module(_pkg)

    # Also register submodules
    for submod_name in ["providers", "profile", "nodes_profile", "nodes_save", "nodes_load", "nodes_browse"]:
        submod_path = pkg_root / f"{submod_name}.py"
        if submod_path.exists():
            sub_spec = importlib.util.spec_from_file_location(
                f"comfyui_cloud_storage.{submod_name}",
                str(submod_path),
            )
            sub_mod = importlib.util.module_from_spec(sub_spec)
            sys.modules[f"comfyui_cloud_storage.{submod_name}"] = sub_mod
            sub_spec.loader.exec_module(sub_mod)
