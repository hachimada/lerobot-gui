"""The torch devices this computer has, offered for a command's device (a fact about the machine,
read from torch, like the serial ports and cameras; empty leaves the choice to lerobot)."""

from __future__ import annotations

import functools


@functools.cache
def available() -> tuple[dict, ...]:
    """({"value", "label"}, ...): CUDA (and each GPU when there are several), MPS, XPU, CPU."""
    import torch

    return read(torch)


def read(torch) -> tuple[dict, ...]:
    """What `torch` (the module) reports."""
    out = []
    if torch.cuda.is_available():
        count = torch.cuda.device_count()
        names = [torch.cuda.get_device_name(i) for i in range(count)]
        out.append({"value": "cuda", "label": f"cuda · {names[0]}" if count == 1 else f"cuda · {count} GPUs"})
        if count > 1:
            out += [{"value": f"cuda:{i}", "label": f"cuda:{i} · {name}"} for i, name in enumerate(names)]
    if torch.backends.mps.is_available():
        out.append({"value": "mps", "label": "mps"})
    xpu = getattr(torch, "xpu", None)
    if xpu is not None and xpu.is_available():
        out.append({"value": "xpu", "label": "xpu"})
    out.append({"value": "cpu", "label": "cpu"})
    return tuple(out)
