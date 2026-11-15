"""lerobot's camera types and their settings, for `--robot.cameras` (read from lerobot, cached)."""

from __future__ import annotations

import functools
import importlib
import pkgutil


@functools.cache
def _camera_config() -> type:
    """lerobot's CameraConfig, with every camera type of the installed lerobot registered."""
    import lerobot.cameras as package
    from lerobot.cameras import CameraConfig

    for module in pkgutil.iter_modules(package.__path__):
        if module.ispkg:  # each camera type is a subpackage that registers its config
            importlib.import_module(f"{package.__name__}.{module.name}")
    return CameraConfig


class LerobotCameras:
    """The camera schema the pages build `--robot.cameras` from."""

    def types(self) -> tuple[str, ...]:
        return tuple(sorted(_camera_config().get_known_choices()))

    @functools.cache  # noqa: B019 (one instance, for the process)
    def fields(self, cam_type: str) -> tuple[dict, ...]:
        """The settings of a camera type, like command options: flag (the field), kind, choices, default..."""
        from .options import walk_dataclass

        return tuple(walk_dataclass(_camera_config().get_choice_class(cam_type)))

    def device_field(self, cam_type: str) -> str | None:
        """The setting that says which camera to open: the type's only required one (opencv: index_or_path)."""
        required = [f["flag"] for f in self.fields(cam_type) if f["required"]]
        return required[0] if len(required) == 1 else None


LEROBOT = LerobotCameras()
