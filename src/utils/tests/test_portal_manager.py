# tests/test_portal_manager.py
import unittest
import sys
import types
import tempfile
import json
import io
from keyring.errors import PasswordDeleteError, KeyringError
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

# --------- stub keyring (module + errors submodule) ----------
errors_mod = types.ModuleType('keyring.errors')
class PasswordDeleteError(Exception): pass
class KeyringError(Exception): pass
errors_mod.PasswordDeleteError = PasswordDeleteError
errors_mod.KeyringError = KeyringError

_keyring_store = {}  # {service: {username: secret}}

def kr_set_password(service, username, password):
    _keyring_store.setdefault(service, {})[username] = password

def kr_get_password(service, username):
    return _keyring_store.get(service, {}).get(username)

def kr_delete_password(service, username):
    if service not in _keyring_store or username not in _keyring_store[service]:
        raise PasswordDeleteError("not found")
    del _keyring_store[service][username]

keyring_mod = types.ModuleType('keyring')
keyring_mod.set_password = kr_set_password
keyring_mod.get_password = kr_get_password
keyring_mod.delete_password = kr_delete_password
keyring_mod.errors = errors_mod

sys.modules['keyring'] = keyring_mod
sys.modules['keyring.errors'] = errors_mod

# --------- stub arcgis.gis.GIS ----------
class _FakeUsers:
    def __init__(self, username):
        self.me = type('Me', (), {'username': username})() if username else None

class FakeGIS:
    instances = []

    def __init__(self, url, *args, **kwargs):
        self._url = url
        self.args = args
        self.kwargs = kwargs
        self.properties = {'portalName': 'FakePortal'}
        self.version = '11.1'
        if kwargs.get('anonymous'):
            username = None
        elif args:
            # built_in call: GIS(url, username, password, ...)
            username = args[0]
        else:
            # oauth or others
            username = None
        self.users = _FakeUsers(username)
        FakeGIS.instances.append(self)

gis_mod = types.ModuleType('arcgis.gis')
gis_mod.GIS = FakeGIS
arcgis_pkg = types.ModuleType('arcgis')
arcgis_pkg.gis = gis_mod
sys.modules['arcgis'] = arcgis_pkg
sys.modules['arcgis.gis'] = gis_mod

# --------- import module under test AFTER stubs ---------
import portal_manager


class PortalManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self.tmp.name) / "profiles.json"
        data = {
            "active_profile": "prod",
            "profiles": [
                {
                    "name": "prod",
                    "url": "https://portal.example.gov/portal",
                    "auth_mode": "built_in",
                    "username": "jane",
                    "verify_ssl": True,
                    "proxies": {"http": "http://proxy", "https": "http://proxy"},
                    "token_lifetime": 120,
                    "set_active_on_connect": True
                },
                {
                    "name": "stage-oauth",
                    "url": "https://stage.example.gov/portal",
                    "auth_mode": "oauth",
                    "client_id": "app123",
                    "redirect_uri": "http://localhost/cb",
                    "uses_client_secret": True,
                    "verify_ssl": True
                },
                {
                    "name": "public",
                    "url": "https://www.arcgis.com",
                    "auth_mode": "anonymous",
                    "verify_ssl": True
                }
            ]
        }
        with open(self.cfg, "w", encoding="utf-8") as f:
            json.dump(data, f)

        FakeGIS.instances.clear()
        _keyring_store.clear()
        self.mgr = portal_manager.PortalManager(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    # ---------- CLI ----------
    def test_help_no_args(self):
        argv = sys.argv
        sys.argv = ['portal_manager.py']
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                portal_manager._cli()
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("Manage ArcGIS Enterprise portal profiles", out.getvalue() + err.getvalue())
        sys.argv = argv

    def test_cli_store_and_ping(self):
        argv = sys.argv
        try:
            # set-password
            sys.argv = ['portal_manager.py', '-c', str(self.cfg),
                        'set-password', 'prod', 'jane', 'PW']
            out = io.StringIO()
            with redirect_stdout(out):
                portal_manager._cli()
            self.assertIn("stored", out.getvalue())

            # ping
            sys.argv = ['portal_manager.py', '-c', str(self.cfg), 'ping', '-n', 'prod']
            out2 = io.StringIO()
            with redirect_stdout(out2):
                portal_manager._cli()
            data = json.loads(out2.getvalue())
            self.assertTrue(data['connected'])
            self.assertEqual(data['user'], 'jane')

            # list
            sys.argv = ['portal_manager.py', '-c', str(self.cfg), 'list']
            out3 = io.StringIO()
            with redirect_stdout(out3):
                portal_manager._cli()
            listing = json.loads(out3.getvalue())
            self.assertEqual(listing['active'], 'prod')
            self.assertGreaterEqual(len(listing['profiles']), 3)
        finally:
            sys.argv = argv

    # ---------- Manager: built-in ----------
    def test_connect_built_in_and_cache(self):
        self.mgr.set_built_in_credentials('prod', 'jane', 'PW')
        gis1 = self.mgr.connect('prod')
        self.assertIsInstance(gis1, FakeGIS)
        self.assertEqual(gis1.users.me.username, 'jane')
        self.assertIn('expiration', gis1.kwargs)
        self.assertIn('proxies', gis1.kwargs)

        # cache reuse
        gis2 = self.mgr.connect('prod')
        self.assertIs(gis1, gis2)

        # force_new breaks cache
        gis3 = self.mgr.connect('prod', force_new=True)
        self.assertIsNot(gis1, gis3)

    def test_clear_password_and_connect_fails(self):
        # clearing when nothing stored should not raise
        self.mgr.clear_built_in_credentials('prod')
        # store then clear
        self.mgr.set_built_in_credentials('prod', 'jane', 'PW')
        self.mgr.clear_built_in_credentials('prod')
        with self.assertRaises(portal_manager.PortalConfigError):
            self.mgr.connect('prod')

    # ---------- Manager: OAuth ----------
    def test_connect_oauth_with_secret(self):
        self.mgr.set_oauth_client_secret('stage-oauth', 'app123', 'sek')
        gis = self.mgr.connect('stage-oauth')
        self.assertEqual(gis.kwargs.get('client_id'), 'app123')
        self.assertEqual(gis.kwargs.get('client_secret'), 'sek')
        self.assertEqual(gis.kwargs.get('redirect_uri'), 'http://localhost/cb')

    def test_connect_oauth_missing_secret_raises(self):
        mgr2 = portal_manager.PortalManager(self.cfg)  # no secret stored in fresh manager
        with self.assertRaises(portal_manager.PortalConfigError):
            mgr2.connect('stage-oauth')

    # ---------- ping ----------
    def test_ping(self):
        self.mgr.set_built_in_credentials('prod', 'jane', 'PW')
        info = self.mgr.ping('prod')
        self.assertTrue(info['connected'])
        self.assertEqual(info['user'], 'jane')
        self.assertEqual(info['profile'], 'prod')


if __name__ == "__main__":
    unittest.main(verbosity=2)
