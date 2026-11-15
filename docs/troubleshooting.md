# Troubleshooting

| Symptom | |
|---|---|
| "The frontend isn't built" | `npm ci && npm run build` in `frontend/` ([install](install.md#1-build-the-frontend)). |
| Datasets or calibration files aren't where you expect | *Environment* shows the dirs lerobot uses. The commands get the GUI's environment as it was at its start: restart it after changing it. |
| `Permission denied: '/dev/ttyACM0'` | The `dialout` group ([install](install.md#3-serial-port-permission)). |
| An arm has a new number after replugging | The GUI flags it, with a button that follows it to the new number. |
| Cameras look swapped after replugging | Their numbers changed: run *Find cameras* again and name them from the new frames. |
| *Check arms*: "motors hold another arm's calibration" | The ports are swapped, or an earlier run with swapped ports wrote the other arm's file into this one. The result says what to do. |
| Can't log out of Hugging Face | The token comes from `HF_TOKEN` in the environment: unset it. |
| Installing `lerobot[all]` fails building `egl-probe` (CMake) | Add `[tool.uv.extra-build-variables] egl-probe = { CMAKE_POLICY_VERSION_MINIMUM = "3.5" }` to your `pyproject.toml` (lerobot-gui's own has it). |
