"""The shapes the API answers with, declared once.

Each route checks what it returns against its shape: a key that isn't declared is an error (FastAPI
answers 500), not dropped, so the tests catch a shape that drifts. The code that builds them is
checked against them too (pyright), and the frontend's types are generated from the OpenAPI these
make (`frontend/openapi.json`, `frontend/src/api/schema.ts`; see `npm run gen:api`).

A key that may be missing is `NotRequired`; one that is always there but may be empty is `X | None`.
The docstring under a key describes it (it reaches the TypeScript types).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, NotRequired, TypedDict

from pydantic import ConfigDict, Field, with_config

SHAPE = ConfigDict(extra="forbid", use_attribute_docstrings=True)

Level = Literal["err", "warn", "info"]
StatusLevel = Literal["ok", "warn", "err", "todo"]

# ---------------------------------------------------------------- actions


@with_config(SHAPE)
class GoAction(TypedDict):
    """Open a page."""

    type: Literal["go"]
    page: str
    label: str


@with_config(SHAPE)
class SetAction(TypedDict):
    """Change a page's values (None clears one)."""

    type: Literal["set"]
    page: str
    values: dict[str, Any]
    label: str
    go: NotRequired[str]
    """the page opened then"""
    toast: NotRequired[str]
    """said once the values are set"""


@with_config(SHAPE)
class HardwareAction(TypedDict):
    """Change Hardware values (None clears one). The Check arms result goes, unless `keep_check`."""

    type: Literal["hardware"]
    values: dict[str, Any]
    label: str
    toast: NotRequired[str]
    """said once the values are set"""
    keep_check: NotRequired[bool]
    """the Check arms result stays (the change doesn't move an arm)"""


@with_config(SHAPE)
class CheckArmsAction(TypedDict):
    """Run Check arms on the Hardware page."""

    type: Literal["check_arms"]
    label: str


@with_config(SHAPE)
class ScrollAction(TypedDict):
    """Bring a card of the current page into view."""

    type: Literal["scroll"]
    target: str
    """the card's element id"""
    label: str


@with_config(SHAPE)
class RunForceAction(TypedDict):
    """Run again without the swapped-arms check."""

    type: Literal["run_force"]
    label: str
    confirm: NotRequired[str]
    """asked before"""


#: what a message's button does
Action = Annotated[
    GoAction | SetAction | HardwareAction | CheckArmsAction | ScrollAction | RunForceAction,
    Field(discriminator="type"),
]


@with_config(SHAPE)
class Message(TypedDict):
    level: Level
    text: str
    actions: list[Action]


@with_config(SHAPE)
class Ok(TypedDict):
    ok: bool


# ------------------------------------------------------------------ pages


@with_config(SHAPE)
class PageMeta(TypedDict):
    id: str
    title: str
    icon: str
    nav: str | None
    """the sidebar section (None: not in the sidebar)"""
    exe: str | None
    """the command it runs"""
    desc: str
    hints: list[str]
    hardware: bool
    """its command uses the robot or the cameras (one such command runs at a time)"""
    presets: bool
    """its values can be saved under a name"""


@with_config(SHAPE)
class Pages(TypedDict):
    pages: list[PageMeta]
    nav: list[str]
    """the sidebar sections, in order"""


# ------------------------------------------------------------------- forms


@with_config(SHAPE)
class Option(TypedDict):
    value: str
    label: str
    disabled: bool
    title: str


@with_config(SHAPE)
class OptionGroup(TypedDict):
    group: str
    items: list[Option]


#: text / number / bool (default, true or false) / toggle (a switch: on writes `--<key>=true`, off leaves the flag
#: out) / choice (a select) / seg (buttons, GUI choices) / picker (a policy: pick Hub or local, then search;
#: `options` are the local ones)
FieldKind = Literal["text", "number", "bool", "toggle", "choice", "seg", "picker"]


@with_config(SHAPE)
class Also(TypedDict):
    """Values stored along with a field's: `values[v]` for the value `v`, else `other`."""

    values: dict[str, dict[str, Any]]
    other: dict[str, Any]


@with_config(SHAPE)
class FieldSpec(TypedDict):
    """One lerobot flag (key = the flag without `--`), or a choice of the GUI itself (`gui`, key `gui.*`). A flag
    goes into the command only when it has a value; empty means lerobot's default."""

    key: str
    label: str
    kind: FieldKind
    gui: bool
    """a choice of the GUI itself (always has a value), not a lerobot flag"""
    flag: str | None
    """shown next to the label"""
    value: Any
    """the value entered (None: none), or the GUI choice"""
    default: str | None
    """lerobot's default (read from the installed lerobot), or the GUI choice's default"""
    required: bool
    options: list[Option | OptionGroup]
    help: str | None
    placeholder: str
    """an example, when lerobot has no default to show"""
    custom: bool
    """choice: also takes a typed value"""
    hub: bool
    """picker: models on the Hugging Face Hub are offered too"""
    mono: bool
    half: bool
    advanced: bool
    suggest: list[str]
    """values offered as one-click chips"""
    also: Also | None
    """values stored along with the field's (a Hardware port: the board on it)"""


@with_config(SHAPE)
class GroupSpec(TypedDict):
    title: str
    fields: list[FieldSpec]


@with_config(SHAPE)
class OptionsQuery(TypedDict):
    """Which `--help` options apply: the selected choice types and the policy to read defaults from."""

    command: str
    selections: dict[str, str]
    policy_path: str | None


@with_config(SHAPE)
class CommandLine(TypedDict):
    exe: str
    args: list[str]
    preview: str
    """as a shell would show it"""


@with_config(SHAPE)
class SummaryChip(TypedDict):
    label: str
    value: str


@with_config(SHAPE)
class FormResponse(TypedDict):
    page: str
    groups: list[GroupSpec]
    values: dict[str, Any]
    hardware_summary: list[SummaryChip]
    """the arms and cameras the command uses"""
    command: CommandLine | None
    messages: list[Message]
    errors: int
    options_query: OptionsQuery | None
    listing_ready: bool
    """lerobot's defaults and choices are known (its options were listed)"""


@with_config(SHAPE)
class OptionInfo(TypedDict):
    """One option of a command, as the installed lerobot lists it."""

    flag: str
    kind: Literal["bool", "int", "float", "str", "json", "enum", "choice"]
    choices: list[str] | None
    default: str | None
    selected: NotRequired[str | None]
    """a choice type: the one selected"""
    required: NotRequired[bool]
    optional: bool
    type: NotRequired[str]
    help: str
    positional: NotRequired[bool]
    """an argparse command's positional argument (not `--flag=value`)"""


@with_config(SHAPE)
class OptionsListing(TypedDict):
    options: list[OptionInfo]
    errors: list[str]


# ---------------------------------------------------------------- hardware


@with_config(SHAPE)
class Role(TypedDict):
    """An arm: follower or leader."""

    name: str
    label: str


@with_config(SHAPE)
class Tty(TypedDict):
    """A port plugged in, and what can be done with it (the server works the values out)."""

    tty: str
    board: str | None
    serial: str | None
    roles: list[str]
    """the arms on it"""
    assign: dict[str, Action]
    """arm -> putting it on this port (the other arm, if it is here, gets its port)"""
    confirm: dict[str, Action]
    """arm on it -> remembering its board (not remembered yet)"""


@with_config(SHAPE)
class StatusItem(TypedDict):
    level: StatusLevel
    text: str
    actions: list[Action]


CalibrationFile = with_config(SHAPE)(TypedDict("CalibrationFile", {"class": str, "id": str}))


@with_config(SHAPE)
class Calibrations(TypedDict):
    """The calibration files lerobot keeps, by kind."""

    robots: list[CalibrationFile]
    teleoperators: list[CalibrationFile]


@with_config(SHAPE)
class ArmGuide(TypedDict):
    """What a Check arms result means and what to do about it."""

    level: Literal["ok", "warn", "err"]
    title: str
    text: str
    steps: NotRequired[list[str]]
    actions: NotRequired[list[Action]]


@with_config(SHAPE)
class ArmResult(TypedDict):
    role: str
    port: str
    id: str
    file: str
    """its calibration file"""
    status: Literal["ok", "other", "mismatch", "no_file", "error"]
    detail: str
    other_role: NotRequired[str]
    """other: the arm whose calibration the motors hold"""
    other_id: NotRequired[str]
    guide: NotRequired[ArmGuide]
    """on the Hardware page"""


@with_config(SHAPE)
class ArmCheck(TypedDict):
    """What the arms' motors hold, compared with the calibration files."""

    arms: list[ArmResult]
    swapped: bool
    remember: NotRequired[Action | None]
    """Check arms only: remembers the boards of the arms found on the right port"""


@with_config(SHAPE)
class HardwareView(TypedDict):
    """Everything the Hardware page shows besides its fields."""

    roles: list[Role]
    ttys: list[Tty]
    camera_names: list[str]
    """names offered: the ones the trained policies and datasets expect"""
    status: list[StatusItem]
    arm_check: ArmCheck | None
    arm_explain: str
    calibrations: Calibrations
    camera_types: list[str]
    """the camera types of the installed lerobot"""
    camera_fields: dict[str, list[FieldSpec]]
    """each type's settings"""
    camera_device_field: dict[str, str | None]
    """each type's setting naming the device"""


@with_config(SHAPE)
class HardwareForm(TypedDict):
    """The Hardware page: each arm's port and calibration id, and everything else it shows."""

    groups: list[GroupSpec]
    view: HardwareView


@with_config(SHAPE)
class Port(TypedDict):
    """A serial port: its name as lerobot-find-port reports it, its other names, the board on it (its identity) and
    the board's serial."""

    tty: str
    aliases: list[str]
    board: str | None
    serial: str | None


@with_config(SHAPE)
class Ports(TypedDict):
    ports: list[Port]
    calibrations: Calibrations


@with_config(SHAPE)
class Discover(TypedDict):
    """A rescan: the ports, and how many datasets and training runs were found."""

    ports: list[Port]
    calibrations: Calibrations
    datasets: int
    policies: int
    local: LocalNames
    """names found on disk"""


@with_config(SHAPE)
class CapturedImage(TypedDict):
    name: str
    type: str | None
    device: str
    mtime: float
    width: int | None
    """the frame's size, offered as the camera's width and height"""
    height: int | None
    older: NotRequired[bool]
    """left by an earlier Find cameras run, not the last capture's"""


# -------------------------------------------------------------------- jobs


@with_config(SHAPE)
class CalibrationPrompt(TypedDict):
    """lerobot waits at its "use the calibration file?" prompt."""

    role: str | None
    """the arm whose id is in the prompt; None when both arms have that id"""
    id: str
    port: str
    mismatch: bool
    warning: str | None


@with_config(SHAPE)
class Note(TypedDict):
    level: Level
    text: str


@with_config(SHAPE)
class FindPortResult(TypedDict):
    tty: str
    by_id: str | None


@with_config(SHAPE)
class JobInfo(TypedDict):
    id: str
    command: str
    page: str | None
    args: list[str]
    hardware: bool
    started: float
    ended: float | None
    running: bool
    returncode: int | None
    stop_requested: bool
    preflight: ArmCheck | None
    """the arm check before it started"""
    preflight_notes: list[Note]
    failure: str | None
    """why it failed (not for a Stop)"""
    prompt: CalibrationPrompt | None
    phase: Literal["scan", "unplug", "reported"] | None
    """lerobot-find-port: where it is"""
    find_port: FindPortResult | None
    """lerobot-find-port: the port it reported"""


# ----------------------------------------------------------------- presets


@with_config(SHAPE)
class PresetInfo(TypedDict):
    name: str
    saved: float | None
    count: int
    """how many values it sets"""


@with_config(SHAPE)
class Preset(TypedDict):
    """A command page's values saved under a name."""

    name: str
    saved: float | None
    values: dict[str, Any]


# --------------------------------------------------------------- accounts


@with_config(SHAPE)
class AccountStatus(TypedDict):
    logged_in: bool
    user: NotRequired[str | None]
    orgs: NotRequired[list[str]]
    token_name: NotRequired[str | None]
    token_role: NotRequired[str | None]
    error: NotRequired[str]
    where: NotRequired[str]
    """where the login comes from"""


@with_config(SHAPE)
class LocalNames(TypedDict):
    """Dataset / model namespaces and Trackio projects and Spaces found on disk."""

    hf_namespaces: list[str]
    trackio_projects: list[str]
    trackio_spaces: list[str]


@with_config(SHAPE)
class Accounts(TypedDict):
    hf: AccountStatus


# ------------------------------------------------------------- environment


@with_config(SHAPE)
class Location(TypedDict):
    name: str
    value: NotRequired[str]
    read_from: NotRequired[str]
    from_env: NotRequired[bool]
    error: NotRequired[str]


@with_config(SHAPE)
class Variable(TypedDict):
    """An environment variable the commands get. A secret's value is never sent."""

    name: str
    set: bool
    secret: bool
    value: str | None
    note: str | None
    """a service's credential variable: which login the commands use"""


@with_config(SHAPE)
class NameValue(TypedDict):
    name: str
    value: str


@with_config(SHAPE)
class EnvironmentInfo(TypedDict):
    """The environment the commands run in."""

    locations: list[Location]
    variables: list[Variable]
    runtime: list[NameValue]


# --------------------------------------------------------- Hugging Face


@with_config(SHAPE)
class LocalDataset(TypedDict):
    repo_id: str
    path: str
    fps: int | float | None
    episodes: int | None
    frames: int | None
    robot_type: str | None
    cameras: list[str]
    tasks: list[str]
    mtime: float
    size: int


LocalCalibration = with_config(SHAPE)(
    TypedDict("LocalCalibration", {"kind": str, "class": str, "id": str, "path": str})
)


@with_config(SHAPE)
class CachedRepo(TypedDict):
    repo_id: str
    repo_type: str
    size: int
    files: int
    revisions: int
    last_accessed: float | None
    last_modified: float | None


@with_config(SHAPE)
class Cache(TypedDict):
    name: str
    path: str | None
    size: int
    repos: list[CachedRepo]
    error: str | None


@with_config(SHAPE)
class HfLocal(TypedDict):
    """What lerobot and huggingface_hub keep on this computer."""

    home: str
    datasets: list[LocalDataset]
    calibrations: list[LocalCalibration]
    caches: list[Cache]
    message: NotRequired[str]
    """after a delete"""


@with_config(SHAPE)
class HubRepo(TypedDict):
    id: str
    private: bool
    downloads: int
    likes: int
    updated: str | None
    url: str


@with_config(SHAPE)
class Owner(TypedDict):
    owner: str
    kind: Literal["user", "org"]
    datasets: list[HubRepo]
    models: list[HubRepo]
    error: str | None


@with_config(SHAPE)
class HfCloud(TypedDict):
    """The account's and its organizations' datasets and models on the Hub."""

    logged_in: bool
    owners: list[Owner]


@with_config(SHAPE)
class HubModel(TypedDict):
    id: str
    downloads: int
    likes: int
    created: str | None
    private: bool


@with_config(SHAPE)
class HubModelGroup(TypedDict):
    title: str
    author: str
    models: list[HubModel]


@with_config(SHAPE)
class HubModels(TypedDict):
    groups: list[HubModelGroup]
    error: str | None
