# tests/test_live_portal_manager.py
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Hard dependency checks
try:
    import keyring
    from keyring.errors import PasswordDeleteError, KeyringError
except Exception as e:  # pragma: no cover
    pytest.skip(f"keyring not available: {e}", allow_module_level=True)

try:
    from arcgis.gis import GIS
except Exception as e:  # pragma: no cover
    pytest.skip(f"arcgis API not available: {e}", allow_module_level=True)

import portal_manager


# ---------------------------
# Environment-driven settings
# ---------------------------
# Required for built-in test
PM_PROFILE_BUILTIN = os.getenv("PM_PROFILE_BUILTIN")          # e.g., "prod"
PM_ENTERPRISE_URL = os.getenv("PM_ENTERPRISE_URL")            # e.g., "https://portal.example.gov/portal"
PM_USERNAME = os.getenv("PM_USERNAME")                        # built-in user
PM_PASSWORD = os.getenv("PM_PASSWORD")                        # built-in password

# Optional OAuth test (disabled by default)
PM_RUN_OAUTH = os.getenv("PM_RUN_OAUTH", "0") == "1"
PM_PROFILE_OAUTH = os.getenv("PM_PROFILE_OAUTH")              # e.g., "stage-oauth"
PM_CLIENT_ID = os.getenv("PM_CLIENT_ID")                      # OAuth app client id
PM_REDIRECT_URI = os.getenv("PM_REDIRECT_URI")                # redirect URI registered with the app
PM_CONFIDENTIAL = os.getenv("PM_CONFIDENTIAL", "0") == "1"    # if true, uses client secret from keyring
PM_CLIENT_SECRET = os.getenv("PM_CLIENT_SECRET")              # required if PM_CONFIDENTIAL=1

# Anonymous always available
PM_PUBLIC_URL = "https://www.arcgis.com"


# ---------------------------
# Fixtures
# ---------------------------
@pytest.fixture(scope="session")
def live_config_path(tmp_path_factory):
    """
    Writes a runtime JSON config using env vars and returns the path.
    No secrets stored in the file. Secrets go to keyring.
    """
    tmpdir = tmp_path_factory.mktemp("pm_live_cfg")
    cfg_path = tmpdir / "profiles.json"

    profiles = []

    # built-in profile if env provided
    if PM_PROFILE_BUILTIN and PM_ENTERPRISE_URL:
        profiles.append({
            "name": PM_PROFILE_BUILTIN,
            "url": PM_ENTERPRISE_URL,
            "auth_mode": "built_in",
            "username": PM_USERNAME,
            "verify_ssl": True,
            "token_lifetime": 120,
            "set_active_on_connect": True
        })

    # oauth profile if requested
    if PM_RUN_OAUTH and PM_PROFILE_OAUTH and PM_ENTERPRISE_URL and PM_CLIENT_ID:
        profiles.append({
            "name": PM_PROFILE_OAUTH,
            "url": PM_ENTERPRISE_URL,
            "auth_mode": "oauth",
            "client_id": PM_CLIENT_ID,
            "redirect_uri": PM_REDIRECT_URI,
            "uses_client_secret": PM_CONFIDENTIAL,
            "verify_ssl": True
        })

    # anonymous ArcGIS Online
    profiles.append({
        "name": "public",
        "url": PM_PUBLIC_URL,
        "auth_mode": "anonymous",
        "verify_ssl": True
    })

    data = {
        "active_profile": PM_PROFILE_BUILTIN or ("public"),
        "profiles": profiles
    }
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return cfg_path


@pytest.fixture(scope="session")
def mgr(live_config_path):
    return portal_manager.PortalManager(live_config_path)


# ---------------------------
# Tests: Anonymous AOG
# ---------------------------
def test_connect_anonymous_aog(mgr):
    gis = mgr.connect("public")
    assert isinstance(gis, GIS)
    # Fetch org name and a small public search to validate live call
    assert "arcgis" in gis.url.lower()
    res = gis.content.search("USA", item_type="Feature Layer", max_items=1)
    assert isinstance(res, list)
    # ping path should report anonymous
    info = mgr.ping("public")
    assert info["connected"] is True
    assert info["user"] in (None, "anonymous", "anonymous_user") or info["user"] == "anonymous"


# ---------------------------
# Tests: Built-in Enterprise
# ---------------------------
built_in_missing = not all([PM_PROFILE_BUILTIN, PM_ENTERPRISE_URL, PM_USERNAME, PM_PASSWORD])

@pytest.mark.skipif(built_in_missing, reason="Built-in env vars not set")
def test_set_password_and_connect_built_in(mgr):
    # store creds to keyring
    mgr.set_built_in_credentials(PM_PROFILE_BUILTIN, PM_USERNAME, PM_PASSWORD)

    gis = mgr.connect(PM_PROFILE_BUILTIN)
    assert isinstance(gis, GIS)
    me = gis.users.me
    assert me is not None
    assert me.username.lower() == PM_USERNAME.lower()

    # verify cache reuse
    cached = mgr.connect(PM_PROFILE_BUILTIN)
    assert gis is cached

    # health check
    info = mgr.ping(PM_PROFILE_BUILTIN)
    assert info["connected"] is True
    assert info["user"].lower() == PM_USERNAME.lower()


@pytest.mark.skipif(built_in_missing, reason="Built-in env vars not set")
def test_clear_password_blocks_login(mgr):
    mgr.set_built_in_credentials(PM_PROFILE_BUILTIN, PM_USERNAME, PM_PASSWORD)
    mgr.clear_built_in_credentials(PM_PROFILE_BUILTIN)
    with pytest.raises(portal_manager.PortalConfigError):
        mgr.connect(PM_PROFILE_BUILTIN)


# ---------------------------
# Tests: OAuth Enterprise
# ---------------------------
oauth_missing = not (PM_RUN_OAUTH and PM_PROFILE_OAUTH and PM_ENTERPRISE_URL and PM_CLIENT_ID)

@pytest.mark.skipif(oauth_missing, reason="OAuth test disabled or env vars missing")
def test_oauth_connect(mgr):
    if PM_CONFIDENTIAL:
        assert PM_CLIENT_SECRET, "PM_CLIENT_SECRET required when PM_CONFIDENTIAL=1"
        mgr.set_oauth_client_secret(PM_PROFILE_OAUTH, PM_CLIENT_ID, PM_CLIENT_SECRET)

    gis = mgr.connect(PM_PROFILE_OAUTH)
    # OAuth may return anonymous until browser auth completes.
    # ArcGIS API for Python opens a browser window. Manual interaction required once.
    # After token is established, users.me is non-None.
    try:
        me = gis.users.me
        # both anonymous and authenticated are acceptable here; just ensure call works
        _ = getattr(me, "username", "anonymous")
    finally:
        info = mgr.ping(PM_PROFILE_OAUTH)
        assert info["connected"] is True


# ---------------------------
# Tests: CLI smoke
# ---------------------------
def test_cli_help_no_args(capsys, monkeypatch):
    # simulate `python portal_manager.py`
    monkeypatch.setenv("PYTHONWARNINGS", "ignore")
    argv = sys.argv
    sys.argv = ["portal_manager.py"]
    with pytest.raises(SystemExit) as cm:
        portal_manager._cli()
    sys.argv = argv
    assert cm.value.code == 0
    out = capsys.readouterr()
    assert "Manage ArcGIS Enterprise portal profiles" in (out.out + out.err)


@pytest.mark.skipif(built_in_missing, reason="Built-in env vars not set")
def test_cli_list_and_ping(live_config_path, capsys, monkeypatch):
    # store password first so ping works
    pm = portal_manager.PortalManager(live_config_path)
    pm.set_built_in_credentials(PM_PROFILE_BUILTIN, PM_USERNAME, PM_PASSWORD)

    argv = sys.argv
    try:
        # list
        sys.argv = ["portal_manager.py", "-c", str(live_config_path), "list"]
        portal_manager._cli()
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["active"] in (PM_PROFILE_BUILTIN, "public")

        # ping
        sys.argv = ["portal_manager.py", "-c", str(live_config_path), "ping", "-n", PM_PROFILE_BUILTIN]
        portal_manager._cli()
        ping_out = capsys.readouterr().out
        info = json.loads(ping_out)
        assert info["connected"] is True
        assert info["user"].lower() == PM_USERNAME.lower()
    finally:
        sys.argv = argv
