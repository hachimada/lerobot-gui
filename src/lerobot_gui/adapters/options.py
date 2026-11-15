"""Every CLI option of a lerobot command, like `--help`, but expanded only for the selected
choice types (robot.type, teleop.type, policy.type, strategy.type, inference.type, ...).

draccus `--help` lists the fields of *every* registered subclass, so this walks the config
dataclasses directly instead and reads the help text with draccus' own docstring helper.
Imports lerobot lazily (first call takes a few seconds) and caches the results.

A listing for a pretrained policy shows its config's defaults. A Hub policy's config is fetched
outside the locks: while one page waits on the Hub (it retries for some 20 s when it can't be
reached), the other listings, and Run, go on.
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import functools
import importlib
import json
import operator
import pathlib
import threading
import time
import types
import typing
from collections.abc import Callable
from typing import Any

from ..cache import Cache

CONFIG_COMMANDS: dict[str, tuple[str, str, str]] = {
    # command: (module that registers robots/teleops/cameras, config module, config class)
    "lerobot-rollout": ("lerobot.scripts.lerobot_rollout", "lerobot.rollout.configs", "RolloutConfig"),
    "lerobot-train": ("lerobot.scripts.lerobot_train", "lerobot.configs.train", "TrainPipelineConfig"),
    "lerobot-record": ("lerobot.scripts.lerobot_record", "lerobot.scripts.lerobot_record", "RecordConfig"),
    "lerobot-teleoperate": (
        "lerobot.scripts.lerobot_teleoperate",
        "lerobot.scripts.lerobot_teleoperate",
        "TeleoperateConfig",
    ),
    "lerobot-calibrate": ("lerobot.scripts.lerobot_calibrate", "lerobot.scripts.lerobot_calibrate", "CalibrateConfig"),
}

#: commands whose arguments are an argparse parser built in their main() (no config class)
ARGPARSE_COMMANDS: dict[str, str] = {
    "lerobot-find-cameras": "lerobot.scripts.lerobot_find_cameras",
}

#: lerobot's imports and the walk over its configs, one at a time
_LOCK = threading.Lock()
#: reading a policy's config, one at a time: draccus sets its config file type process-wide meanwhile
_POLICY_LOCK = threading.Lock()
#: a listing whose policy config couldn't be read is built again after this (the Hub may be back)
RETRY_AFTER_S = 60.0


def _listings(clock: Callable[[], float] = time.monotonic) -> Cache[str, tuple[dict, bool]]:
    """The listings built (with whether they have their policy config), kept for good once complete."""
    return Cache(lambda built: None if built[1] else RETRY_AFTER_S, clock)


_LISTINGS = _listings()
_MISSING = object()


def list_options(command: str, selections: dict[str, str] | None = None, policy_path: str | None = None) -> dict:
    """{"options": [...], "errors": [...]} for `command`.

    selections maps a choice field (e.g. "robot", "policy", "inference") to the chosen type name.
    policy_path loads that pretrained config so `--policy.*` defaults show the checkpoint's values.
    """
    if command in ARGPARSE_COMMANDS:
        return _LISTINGS.get(command, lambda: _argparse_listing(command))[0]
    if command not in CONFIG_COMMANDS:
        raise ValueError(f"No option schema for {command}")
    selections = {k: v for k, v in (selections or {}).items() if v}
    key = _key(command, selections, policy_path)
    return _LISTINGS.get(key, lambda: _build(command, selections, policy_path))[0]


def cached_options(
    command: str, selections: dict[str, str] | None = None, policy_path: str | None = None
) -> dict | None:
    """The listing if it was built already, else None (doesn't import lerobot's commands). An argparse
    command's listing is quick to build, so it is built here."""
    if command in ARGPARSE_COMMANDS:
        return list_options(command)
    selections = {k: v for k, v in (selections or {}).items() if v}
    built = _LISTINGS.fresh(_key(command, selections, policy_path))
    return built[0] if built is not None else None


def _key(command: str, selections: dict[str, str], policy_path: str | None) -> str:
    return json.dumps([command, sorted(selections.items()), policy_path or ""])


def _argparse_listing(command: str) -> tuple[dict, bool]:
    with _LOCK:
        return {"options": _argparse_options(ARGPARSE_COMMANDS[command]), "errors": []}, True


def _build(command: str, selections: dict[str, str], policy_path: str | None) -> tuple[dict, bool]:
    """The listing, and whether it has its policy config (when one was asked for)."""
    with _LOCK:
        cls = _config_class(command)
    errors: list[str] = []
    instances: dict[str, Any] = {}
    complete = True
    if policy_path:
        try:
            instances["policy"] = _policy_config(policy_path)
        except Exception as exc:  # bad path / no network: fall back to class defaults
            from ..paths import tilde

            errors.append(f"Could not read the policy config from {tilde(policy_path)}: {exc}")
            complete = False
    out: list[dict] = []
    with _LOCK:
        _walk(cls, None, "", selections, instances, out, errors)
    return {"options": out, "errors": errors}, complete


def _config_class(command: str) -> type:
    import lerobot.policies  # noqa: F401  registers the policy configs

    register_mod, cfg_mod, cfg_name = CONFIG_COMMANDS[command]
    importlib.import_module(register_mod)
    return getattr(importlib.import_module(cfg_mod), cfg_name)


def _policy_config(path: str) -> Any:
    """A pretrained policy's config, as lerobot reads it. A Hub policy's config is fetched first,
    outside the locks (it may wait on the Hub); then it is read from the Hugging Face cache."""
    hub = not pathlib.Path(path).is_dir()
    if hub:
        _fetch_policy_config(path)
    with _POLICY_LOCK:
        return _read_policy_config(path, cached_only=hub)


def _fetch_policy_config(repo_id: str) -> None:
    """Put a Hub policy's config into the Hugging Face cache: the file lerobot's from_pretrained
    downloads, with the function it uses (raises what it would)."""
    from lerobot.configs import policies

    policies.hf_hub_download(repo_id=repo_id, filename=policies.CONFIG_NAME)


def _read_policy_config(path: str, *, cached_only: bool) -> Any:
    from lerobot.configs.policies import PreTrainedConfig

    return PreTrainedConfig.from_pretrained(path, local_files_only=cached_only)


class _Captured(Exception):
    pass


def _argparse_parser(module_name: str) -> argparse.ArgumentParser:
    """The parser a lerobot script builds in its main(), taken just before it parses sys.argv."""
    module = importlib.import_module(module_name)
    real = module.argparse
    captured: list[argparse.ArgumentParser] = []

    class Capturing(real.ArgumentParser):
        def parse_args(self, *args, **kwargs):  # type: ignore[override]
            captured.append(self)
            raise _Captured

    # only the script's own reference to argparse is replaced, for the time of the call
    shim = types.ModuleType("argparse")
    shim.__dict__.update(real.__dict__)
    shim.ArgumentParser = Capturing  # type: ignore[attr-defined]
    setattr(module, "argparse", shim)  # noqa: B010
    try:
        module.main()
    except _Captured:
        pass
    finally:
        setattr(module, "argparse", real)  # noqa: B010
    if not captured:
        raise ValueError(f"{module_name}.main() built no argument parser")
    return captured[0]


def _argparse_options(module_name: str) -> list[dict]:
    """The arguments of an argparse script, in the shape of the config options (flag without dashes)."""
    out = []
    for action in _argparse_parser(module_name)._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        positional = not action.option_strings
        flag = action.dest if positional else action.option_strings[-1].lstrip("-")
        if action.choices:
            kind = "enum"
        elif isinstance(action, argparse._StoreTrueAction | argparse._StoreFalseAction):
            kind = "bool"
        else:
            kind = {int: "int", float: "float"}.get(action.type, "str")  # type: ignore[arg-type]
        out.append(
            {
                "flag": flag,
                "kind": kind,
                "choices": [str(c) for c in action.choices] if action.choices else None,
                "default": _fmt(action.default if action.default is not None else _MISSING),
                "required": bool(action.required) and not positional,
                "optional": not action.required,
                "type": getattr(action.type, "__name__", "str") if action.type else "str",
                "help": " ".join((action.help or "").split()),
                "positional": positional,
            }
        )
    return out


def walk_dataclass(cls: type) -> list[dict]:
    """The options of one config dataclass (e.g. a camera config), keyed by field name."""
    out: list[dict] = []
    _walk(cls, None, "", {}, {}, out, [])
    return out


def _help(cls: type, name: str) -> str:
    from draccus.wrappers import docstring

    for klass in getattr(cls, "__mro__", [cls]):
        if (
            not isinstance(klass, type)
            or not dataclasses.is_dataclass(klass)
            or name not in getattr(klass, "__dataclass_fields__", {})
        ):
            continue
        try:
            doc = docstring.get_attribute_docstring(klass, name)
            text = docstring.get_preferred_help_text(doc, preferred_help=docstring.HelpOrder.inline)
        except Exception:
            text = None
        if text:
            return " ".join(text.split())
    return ""


def _field_default(f: dataclasses.Field) -> Any:
    if f.default is not dataclasses.MISSING:
        return f.default
    if f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
        try:
            return f.default_factory()  # type: ignore[misc]
        except Exception:
            return None
    return _MISSING


def _unwrap_optional(t: Any) -> tuple[Any, bool]:
    if typing.get_origin(t) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(t) if a is not type(None)]
        optional = len(args) != len(typing.get_args(t))
        if len(args) == 1:
            return args[0], optional
        return functools.reduce(operator.or_, args), optional
    return t, False


def _is_choice(t: Any) -> bool:
    from draccus.utils import is_choice_type

    try:
        return isinstance(t, type) and is_choice_type(t)
    except Exception:
        return False


def _walk(cls: type, instance: Any, prefix: str, selections: dict, instances: dict, out: list, errors: list) -> None:
    try:
        hints = typing.get_type_hints(cls)
    except Exception:
        hints = {}
    for f in dataclasses.fields(cls):
        if not f.init or f.name.startswith("_"):
            continue
        name = prefix + f.name
        t = hints.get(f.name, f.type)
        default = getattr(instance, f.name, _MISSING) if instance is not None else _field_default(f)
        inner, optional = _unwrap_optional(t)
        help_text = _help(cls, f.name)

        if _is_choice(inner):
            choices = inner.get_known_choices()
            inst = instances.get(name)
            if inst is None and default is not _MISSING and default is not None and isinstance(default, inner):
                inst = default
            default_name = inner.get_choice_name(type(default)) if isinstance(default, inner) else None
            selected = selections.get(name) or (inner.get_choice_name(type(inst)) if inst is not None else None)
            out.append(
                {
                    "flag": f"{name}.type",
                    "kind": "choice",
                    "choices": sorted(choices),
                    "default": default_name,
                    "selected": selected,
                    "optional": optional,
                    "help": help_text or f"Which {inner.__name__} to use",
                }
            )
            if selected in choices:
                sub = choices[selected]
                if inst is not None and type(inst) is not sub:
                    inst = None
                _walk(sub, inst, name + ".", selections, instances, out, errors)
        elif isinstance(inner, type) and dataclasses.is_dataclass(inner):
            inst = default if dataclasses.is_dataclass(default) and not isinstance(default, type) else None
            _walk(inner, inst, name + ".", selections, instances, out, errors)
        else:
            out.append(_leaf(name, inner, optional, default, help_text))


def _leaf(name: str, t: Any, optional: bool, default: Any, help_text: str) -> dict:
    kind, choices = "json", None
    origin = typing.get_origin(t)
    if t is bool:
        kind = "bool"
    elif t is int:
        kind = "int"
    elif t is float:
        kind = "float"
    elif isinstance(t, type) and issubclass(t, enum.Enum):
        kind, choices = "enum", [m.name for m in t]
    elif origin is typing.Literal:
        kind, choices = "enum", [str(a) for a in typing.get_args(t)]
    elif (
        t in (str, pathlib.Path)
        or (isinstance(t, type) and issubclass(t, (str, pathlib.PurePath)))
        or origin in (typing.Union, types.UnionType)
    ):
        kind = "str"
    return {
        "flag": name,
        "kind": kind,
        "choices": choices,
        "default": _fmt(default),
        "required": default is _MISSING,
        "optional": optional,
        "type": _type_name(t, optional),
        "help": help_text,
    }


def _fmt(v: Any) -> str | None:
    if v is _MISSING or v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, enum.Enum):
        return v.name
    if isinstance(v, (str, int, float, pathlib.PurePath)):
        return str(v)
    try:
        from draccus.parsers.encoding import encode

        return json.dumps(encode(v))
    except Exception:
        return str(v)


def _type_name(t: Any, optional: bool) -> str:
    try:
        from draccus.utils import stringify_type

        s = stringify_type(t)
    except Exception:
        s = getattr(t, "__name__", str(t))
    s = s.replace("typing.", "").replace("pathlib.", "")
    return f"{s} | None" if optional else s
