import pytest

from lerobot_gui.adapters import accounts


@pytest.fixture(autouse=True)
def _fresh_cache():
    accounts._cache.clear()
    yield
    accounts._cache.clear()


def test_hf_status_logged_out(monkeypatch):
    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
    assert accounts.hf_status(refresh=True)["logged_in"] is False


def test_hf_status_logged_in(monkeypatch):
    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "get_token", lambda: "hf_x")
    monkeypatch.setattr(
        huggingface_hub,
        "whoami",
        lambda token: {
            "name": "alice",
            "orgs": [{"name": "lab"}],
            "auth": {"accessToken": {"displayName": "gui", "role": "write"}},
        },
    )
    st = accounts.hf_status(refresh=True)
    assert (st["logged_in"], st["user"], st["orgs"], st["token_role"]) == (True, "alice", ["lab"], "write")


def http_error(status: int, message: str):
    """An error as huggingface_hub raises it for an HTTP status (nothing is sent)."""
    import httpx
    from huggingface_hub.errors import HfHubHTTPError

    response = httpx.Response(status, request=httpx.Request("GET", "https://huggingface.co/api/whoami-v2"))
    return HfHubHTTPError(message, response=response)


def test_hf_status_invalid_token(monkeypatch):
    import huggingface_hub

    error = http_error(401, "Invalid user token.")

    def whoami(token):
        raise error

    monkeypatch.setattr(huggingface_hub, "get_token", lambda: "hf_x")
    monkeypatch.setattr(huggingface_hub, "whoami", whoami)
    st = accounts.hf_status(refresh=True)
    assert st["logged_in"] is False and "invalid" in st["error"]
    # told by the status, not the words: another error saying "Invalid" doesn't log out
    error = http_error(503, "Invalid response from the server")
    st = accounts.hf_status(refresh=True)
    assert st["logged_in"] is True and st["error"].startswith("Could not reach Hugging Face")


def test_hf_status_is_cached(monkeypatch):
    import huggingface_hub

    calls = []
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: calls.append(1))
    accounts.hf_status(refresh=True)
    accounts.hf_status()
    assert len(calls) == 1


def test_hf_login_validates_before_saving(monkeypatch):
    import huggingface_hub

    saved = []

    def whoami(token):
        raise RuntimeError("401 Unauthorized")

    monkeypatch.setattr(huggingface_hub, "whoami", whoami)
    monkeypatch.setattr(huggingface_hub, "login", lambda **kw: saved.append(kw))
    with pytest.raises(ValueError, match="rejected"):
        accounts.hf_login("hf_bad")
    with pytest.raises(ValueError):
        accounts.hf_login("   ")
    assert saved == []


def test_logout_refuses_env_credentials(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "x")
    with pytest.raises(ValueError, match="HF_TOKEN"):
        accounts.hf_logout()


def test_hf_logout_is_hf_auth_logout(monkeypatch):
    import huggingface_hub

    calls = []
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(huggingface_hub, "logout", lambda token_name=None: calls.append(token_name))
    monkeypatch.setattr(accounts, "hf_status", lambda refresh=False: {"logged_in": False})
    assert accounts.hf_logout() == {"logged_in": False}
    assert calls == [None]  # all saved tokens, like `hf auth logout`

    def still_logged_in(token_name=None):
        raise OSError("Token has been deleted from your machine but you are still logged in.\nTo log out, ...")

    monkeypatch.setattr(huggingface_hub, "logout", still_logged_in)
    with pytest.raises(ValueError, match="still logged in"):
        accounts.hf_logout()
