"""Adapters around lerobot, draccus, OpenCV and huggingface_hub internals.

Everything that depends on how those libraries work inside lives here, so a version bump is
fixed in one place; tests/contract checks these against the installed versions.
"""
