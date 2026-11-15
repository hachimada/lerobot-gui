"""The Environment page: lerobot's data dirs, the variables that are set (secrets hidden), what runs."""

import pytest

from lerobot_gui.adapters import environment

SECRET = "hf_do_not_show_this_value"


@pytest.fixture
def env(monkeypatch, tmp_path):
    for name in list(environment.os.environ):
        if name.startswith(environment.PREFIXES) or name in environment.ALWAYS:
            monkeypatch.delenv(name)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("HF_TOKEN", SECRET)
    monkeypatch.setenv("HF_ENDPOINT", "https://hub.example")
    monkeypatch.setenv("HF_LEROBOT_HOME", str(tmp_path / "home" / "data"))
    monkeypatch.setenv("TRACKIO_DIR", str(tmp_path / "home" / "trackio"))
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    monkeypatch.setenv("LEROBOT_GUI_TOKEN", "gui-token-value")
    monkeypatch.setenv("SOMETHING_ELSE", "x")
    monkeypatch.setenv("DISPLAY", ":0")
    return monkeypatch


def test_variables_by_prefix_and_the_listed_ones(env):
    found = {v["name"]: v for v in environment.variables()}
    assert set(found) == {
        "CUDA_VISIBLE_DEVICES", "DISPLAY", "HF_ENDPOINT", "HF_LEROBOT_HOME", "HF_TOKEN", "LEROBOT_GUI_TOKEN",
        "TRACKIO_DIR", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE",
    }  # fmt: skip
    assert found["HF_ENDPOINT"] == {
        "name": "HF_ENDPOINT", "set": True, "secret": False, "value": "https://hub.example", "note": None,
    }  # fmt: skip
    assert found["HF_LEROBOT_HOME"]["value"] == "~/data"
    assert found["TRACKIO_DIR"]["value"] == "~/trackio"
    assert found["WAYLAND_DISPLAY"] == {
        "name": "WAYLAND_DISPLAY", "set": False, "secret": False, "value": None, "note": None,
    }  # fmt: skip


def test_secrets_are_never_returned(env, client):
    found = {v["name"]: v for v in environment.variables()}
    for name in ("HF_TOKEN", "LEROBOT_GUI_TOKEN"):
        assert {k: found[name][k] for k in ("set", "secret", "value")} == {"set": True, "secret": True, "value": None}
    text = client.get("/api/environment").text
    assert SECRET not in text and "gui-token-value" not in text


def test_secret_names():
    assert all(environment.is_secret(n) for n in ("HF_TOKEN", "SOME_API_KEY", "MY_SECRET", "DB_PASSWORD"))
    assert not any(environment.is_secret(n) for n in ("HF_HOME", "DISPLAY", "TRACKIO_DIR"))


def test_locations_say_where_each_dir_comes_from(env):
    found = {loc["name"]: loc for loc in environment.locations()}
    assert found["HF_LEROBOT_HOME"]["read_from"] == "lerobot.utils.constants"
    assert found["HF_LEROBOT_HOME"]["from_env"] is True  # HF_LEROBOT_HOME is set
    assert found["HF_LEROBOT_CALIBRATION"]["from_env"] is False
    assert found["HF_HOME"]["read_from"] == "huggingface_hub.constants"


def test_a_dir_that_cannot_be_read_is_reported(monkeypatch):
    def refuse():
        raise ValueError("'LEROBOT_HOME' is deprecated, please use 'HF_LEROBOT_HOME' instead.")

    monkeypatch.setattr(environment, "lerobot_dirs", refuse)
    (error, *rest) = environment.locations()
    assert error == {
        "name": "lerobot.utils.constants",
        "error": "ValueError: 'LEROBOT_HOME' is deprecated, please use 'HF_LEROBOT_HOME' instead.",
    }
    assert [loc["name"] for loc in rest] == ["HF_HOME", "HF_HUB_CACHE"]


def test_the_api_and_the_page(client, settings):
    d = client.get("/api/environment").json()
    assert set(d) == {"locations", "variables", "runtime"}
    runtime = {r["name"]: r["value"] for r in d["runtime"]}
    assert set(runtime) == {"Workspace", "Commands", "Python", "lerobot", "lerobot-gui"}
    pages = {p["id"]: p for p in client.get("/api/pages").json()["pages"]}
    assert pages["environment"]["nav"] == "Setup" and pages["environment"]["exe"] is None


def _note(name):
    return next(v for v in environment.variables() if v["name"] == name)["note"]


def test_the_credential_variables_say_which_login_is_used(monkeypatch, tmp_path):
    import huggingface_hub.constants

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("HF_TOKEN", raising=False)
    token = home / ".cache" / "huggingface" / "token"
    monkeypatch.setattr(huggingface_hub.constants, "HF_TOKEN_PATH", str(token))
    # nothing saved
    assert _note("HF_TOKEN") == "No login is saved either."
    # saved by `hf auth login`
    token.parent.mkdir(parents=True)
    token.write_text("hf_saved_secret")
    assert _note("HF_TOKEN") == "The login saved in `~/.cache/huggingface/token` is used."
    # the variables come first
    monkeypatch.setenv("HF_TOKEN", SECRET)
    assert _note("HF_TOKEN") == "This is the login used: it comes before a saved one."
    text = str(environment.variables())
    assert "hf_saved_secret" not in text and SECRET not in text
    assert _note("DISPLAY") is None


def test_the_page_shows_the_commands_environment(client, monkeypatch):
    # set in the GUI's environment after it started (as a library the GUI uses may do): the commands don't get it
    monkeypatch.setenv("HF_SET_FOR_THE_GUI", "2-12345-unix-/tmp/gui-service")
    names = [v["name"] for v in client.get("/api/environment").json()["variables"]]
    assert "HF_SET_FOR_THE_GUI" not in names
