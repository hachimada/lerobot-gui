# Usage

## First steps

1. **Hardware**
   - *Find port* finds each arm's port (unplug it when asked, then *Enter* or the Enter key);
     *Use as follower* / *Use as leader* assigns it.
   - *Follower & leader*: each arm's port and calibration id. *Check arms* reads the calibration
     stored in the motors (nothing moves) to catch swapped ports, and remembers each arm's USB
     board so a renumbering after replugging is caught.
   - *Find cameras* saves a frame per camera: check the ones to use and name them. The names must
     match the policy's `observation.images.<name>` inputs. Camera numbers can change after
     replugging: run it again then.
   - *Camera settings*: the lerobot settings of each checked camera; *Add manually* for a camera
     Find cameras doesn't list.
2. **Calibrate** each arm once per id.
3. **Teleoperate** to check the setup, then **Record**, **Train** and **Rollout**.

**Services → Hugging Face** logs in and out like `hf auth login` / `hf auth logout` (needed to push
to the Hub or log to a Trackio Space) and lists the datasets and models on this computer and on the
Hub. **Services → Trackio** runs `trackio show` for the runs Train logged with Trackio.
**Environment** shows lerobot's data dirs, the environment variables set, and the lerobot that runs.

## What goes into a command

Only what you enter is written: an empty field leaves its flag out and shows lerobot's default. Two
exceptions: Train's *Resume* adds `--resume=true`, and Record's *Add to an existing dataset* with
the Dataset folder empty writes that dataset's local folder (shown as `auto: …`). Each page has the
common flags as fields and every other `--help` option under *All options*.

*Run* starts the command with its output and an input line for lerobot's prompts. *Enter* sends an
empty line, which is what most of them wait for; the Enter key does the same while no field or
button has the focus. One robot command runs at a time; training can run next to it.

Run is blocked only by malformed input (number, JSON), flags lerobot marks as required, and the
Hardware checks (a port not set, an arm renumbered after replugging, swapped arms). Everything else
is up to lerobot.

## From another computer

The server listens on 127.0.0.1 only, and every API call needs the per-launch token in the page.
Forward the port over SSH and open <http://localhost:7878>:

```bash
ssh -L 7878:127.0.0.1:7878 user@robot-pc
```
