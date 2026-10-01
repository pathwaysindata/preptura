# portal_manager.py
# Purpose: Manage multiple ArcGIS Enterprise Portal connections via profiles.
# Requires: arcgis (ArcGIS API for Python), keyring

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

import keyring
from keyring.errors import PasswordDeleteError, KeyringError
from arcgis.gis import GIS


# ---------- Exceptions ----------
class PortalConfigError(Exception):
    pass


# ---------- Data Model ----------
@dataclass
class PortalProfile:
    """
    Profile metadata (no secrets stored on disk).
    """
    name: str
    url: str
    auth_mode: str = "built_in"  # built_in | oauth | anonymous

    # Built-in auth
    username: Optional[str] = None

    # OAuth
    client_id: Optional[str] = None
    redirect_uri: Optional[str] = None
    # If your OAuth app is confidential, store the secret in keyring. Field below just flags usage.
    uses_client_secret: bool = False

    # Network and behavior
    verify_ssl: Optional[bool | str] = True  # True/False or path to CA bundle
    proxies: Optional[Dict[str, str]] = None
    referer: Optional[str] = None
    token_lifetime: int = 120  # minutes
    set_active_on_connect: bool = False

    # runtime cache (not serialized)
    _cached: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def as_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        d.pop("_cached", None)
        return d


# ---------- Secrets ----------
class SecretStore:
    """
    Stores and retrieves credentials using the OS keyring.
    Per-profile service names to avoid collisions.
    """
    def __init__(self, service_prefix: str = "portal-manager"):
        self.service_prefix = service_prefix

    def _svc(self, profile: str, key: str) -> str:
        return f"{self.service_prefix}:{profile}:{key}"

    # built-in
    def set_password(self, profile: str, username: str, password: str) -> None:
        keyring.set_password(self._svc(profile, "password"), username, password)

    def get_password(self, profile: str, username: str) -> Optional[str]:
        return keyring.get_password(self._svc(profile, "password"), username)

    def clear_password(self, profile: str, username: str) -> None:
        keyring.delete_password(self._svc(profile, "password"), username)

    # oauth client_secret
    def set_client_secret(self, profile: str, client_id: str, client_secret: str) -> None:
        keyring.set_password(self._svc(profile, "client_secret"), client_id, client_secret)

    def get_client_secret(self, profile: str, client_id: str) -> Optional[str]:
        return keyring.get_password(self._svc(profile, "client_secret"), client_id)

    def clear_client_secret(self, profile: str, client_id: str) -> None:
        keyring.delete_password(self._svc(profile, "client_secret"), client_id)


# ---------- Manager ----------
class PortalManager:
    """
    Loads profiles from JSON, returns GIS objects on demand.
    Secrets are stored in OS keyring, not in the JSON file.
    """

    def __init__(self, config_path: str | Path, service_prefix: str = "portal-manager"):
        self.config_path = Path(config_path).expanduser().resolve()
        self._profiles: Dict[str, PortalProfile] = {}
        self._active_name: Optional[str] = None
        self._gis_cache: Dict[str, Tuple[GIS, float]] = {}  # name -> (GIS, created_ts)
        self._secrets = SecretStore(service_prefix)
        self._load()

    # ----- IO -----
    def _load(self) -> None:
        if not self.config_path.exists():
            raise PortalConfigError(f"Config file not found: {self.config_path}")
        with self.config_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        profiles = raw.get("profiles") or []
        if not isinstance(profiles, list) or not profiles:
            raise PortalConfigError("Config 'profiles' must be a non-empty list.")

        self._profiles = {}
        for p in profiles:
            prof = PortalProfile(**p)
            self._profiles[prof.name] = prof

        self._active_name = raw.get("active_profile") or None

    def save(self) -> None:
        data = {
            "active_profile": self._active_name,
            "profiles": [p.as_dict() for p in self._profiles.values()],
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ----- Query -----
    @property
    def profiles(self) -> Dict[str, PortalProfile]:
        return dict(self._profiles)

    @property
    def active_profile_name(self) -> Optional[str]:
        return self._active_name

    def get_profile(self, name: Optional[str] = None) -> PortalProfile:
        n = name or self._active_name
        if not n:
            raise PortalConfigError("No profile name provided and no active profile set.")
        try:
            return self._profiles[n]
        except KeyError:
            raise PortalConfigError(f"Profile '{n}' not found.") from None

    # ----- Mutate -----
    def set_active(self, name: str) -> None:
        if name not in self._profiles:
            raise PortalConfigError(f"Profile '{name}' not found.")
        self._active_name = name
        self.save()

    def add_or_update(self, profile: PortalProfile) -> None:
        self._profiles[profile.name] = profile
        self.save()

    def remove(self, name: str) -> None:
        if name in self._profiles:
            self._profiles.pop(name)
            self._gis_cache.pop(name, None)
            if self._active_name == name:
                self._active_name = None
            self.save()

    # ----- Credentials API (keyring) -----
    def set_built_in_credentials(self, profile_name: str, username: str, password: str) -> None:
        prof = self.get_profile(profile_name)
        if prof.auth_mode != "built_in":
            raise PortalConfigError(f"Profile '{profile_name}' is not built_in.")
        prof.username = username
        self._secrets.set_password(profile_name, username, password)
        self.add_or_update(prof)

    def clear_built_in_credentials(self, profile_name: str) -> None:
        prof = self.get_profile(profile_name)
        if not prof.username:
            return
        try:
            self._secrets.clear_password(profile_name, prof.username)
        except PasswordDeleteError:
            pass

    def set_oauth_client_secret(self, profile_name: str, client_id: str, client_secret: str) -> None:
        prof = self.get_profile(profile_name)
        if prof.auth_mode != "oauth":
            raise PortalConfigError(f"Profile '{profile_name}' is not oauth.")
        prof.client_id = client_id
        prof.uses_client_secret = True
        self._secrets.set_client_secret(profile_name, client_id, client_secret)
        self.add_or_update(prof)

    def clear_oauth_client_secret(self, profile_name: str) -> None:
        prof = self.get_profile(profile_name)
        if prof.client_id:
            try:
                self._secrets.clear_client_secret(profile_name, prof.client_id)
            except PasswordDeleteError:
                pass
        prof.uses_client_secret = False
        self.add_or_update(prof)

    # ----- GIS creation -----
    def connect(self, name: Optional[str] = None, force_new: bool = False) -> GIS:
        prof = self.get_profile(name)

        # reuse cached GIS if available
        if not force_new and prof.name in self._gis_cache:
            return self._gis_cache[prof.name][0]

        common_kwargs = {
            "verify_cert": prof.verify_ssl,
            "profile": None,  # avoid local arcgis profile dirs
            "proxies": prof.proxies,
            "referer": prof.referer,
        }
        common_kwargs = {k: v for k, v in common_kwargs.items() if v is not None}

        auth = prof.auth_mode.lower()

        if auth == "anonymous":
            gis = GIS(prof.url, anonymous=True, **common_kwargs)

        elif auth == "built_in":
            if not prof.username:
                raise PortalConfigError(f"Username missing for built_in profile '{prof.name}'.")
            pw = self._secrets.get_password(prof.name, prof.username)
            if not pw:
                raise PortalConfigError(
                    f"No password found in keyring for profile '{prof.name}' and user '{prof.username}'."
                )
            gis = GIS(
                prof.url,
                prof.username,
                pw,
                expiration=prof.token_lifetime,
                **common_kwargs,
            )

        elif auth == "oauth":
            if not prof.client_id:
                raise PortalConfigError(f"client_id missing for oauth profile '{prof.name}'.")
            oauth_kwargs: Dict[str, Any] = {}
            if prof.redirect_uri:
                oauth_kwargs["redirect_uri"] = prof.redirect_uri
            if prof.uses_client_secret:
                client_secret = self._secrets.get_client_secret(prof.name, prof.client_id)
                if not client_secret:
                    raise PortalConfigError(
                        f"Client secret flagged but not found in keyring for profile '{prof.name}'."
                    )
                oauth_kwargs["client_secret"] = client_secret
            gis = GIS(prof.url, client_id=prof.client_id, **oauth_kwargs, **common_kwargs)

        else:
            raise PortalConfigError(f"Unsupported auth_mode '{prof.auth_mode}' in profile '{prof.name}'.")

        self._gis_cache[prof.name] = (gis, time.time())
        if prof.set_active_on_connect:
            self._active_name = prof.name
            self.save()
        return gis

    # ----- Health checks -----
    def ping(self, name: Optional[str] = None) -> Dict[str, Any]:
        gis = self.connect(name)
        try:
            me = gis.users.me
            org = gis.properties.get("portalName", None)
            version = getattr(gis, "version", None)
            who = me.username if me else "anonymous"
            return {
                "profile": self.get_profile(name).name,
                "connected": True,
                "user": who,
                "org": org,
                "version": str(version) if version else None,
                "base_url": gis._url,
            }
        except Exception as ex:
            return {
                "profile": self.get_profile(name).name,
                "connected": False,
                "error": repr(ex),
            }

    def clear_cache(self) -> None:
        self._gis_cache.clear()


# ---------- CLI ----------
def _print_json(d: Dict[str, Any]) -> None:
    import json as _json
    print(_json.dumps(d, indent=2))


# ---- replace your _cli() with this ----
def _cli():
    import argparse
    import sys
    from textwrap import dedent

    epilog = dedent("""
    Examples:
      portal_manager.py -c ~/.portal_profiles.json list
      portal_manager.py -c ~/.portal_profiles.json set-active prod
      portal_manager.py -c ~/.portal_profiles.json set-password prod jane.doe 'S3curePW'
      portal_manager.py -c ~/.portal_profiles.json ping -n stage-oauth

    Notes:
      - Secrets are stored in the OS keyring, not in the JSON config.
      - OAuth confidential apps: store the client secret via set-client-secret.
    """)

    parser = argparse.ArgumentParser(
        description="Manage ArcGIS Enterprise portal profiles and credentials.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument("-c", "--config", required=False, help="Path to JSON config.")
    parser.add_argument("--version", action="version", version="portal-manager 1.0.0")

    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List profiles.")
    p_set = sub.add_parser("set-active", help="Set active profile.")
    p_set.add_argument("name")

    p_ping = sub.add_parser("ping", help="Ping a profile.")
    p_ping.add_argument("-n", "--name", help="Profile name (defaults to active).")

    p_who = sub.add_parser("whoami", help="Show connected user for a profile.")
    p_who.add_argument("-n", "--name", help="Profile name (defaults to active).")

    # credentials
    p_setpw = sub.add_parser("set-password", help="Store built-in creds in keyring.")
    p_setpw.add_argument("name")
    p_setpw.add_argument("username")
    p_setpw.add_argument("password")

    p_clrpw = sub.add_parser("clear-password", help="Clear built-in creds in keyring.")
    p_clrpw.add_argument("name")

    p_setcs = sub.add_parser("set-client-secret", help="Store OAuth client secret in keyring.")
    p_setcs.add_argument("name")
    p_setcs.add_argument("client_id")
    p_setcs.add_argument("client_secret")

    p_clrcs = sub.add_parser("clear-client-secret", help="Clear OAuth client secret in keyring.")
    p_clrcs.add_argument("name")

    # explicit help subcommand
    sub.add_parser("help", help="Show this help message and exit.")

    # If no args: show help and exit 0 (man-style)
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(0)

    # Parse known args so `help` works without requiring -c
    args = parser.parse_args()

    # If `help` subcommand: show help and exit
    if args.cmd == "help":
        parser.print_help(sys.stderr)
        sys.exit(0)

    # From here on, a config path is required
    if not args.config:
        parser.error("the following arguments are required: -c/--config")

    mgr = PortalManager(args.config)

    if args.cmd == "list":
        data = {
            "active": mgr.active_profile_name,
            "profiles": [p.as_dict() for p in mgr.profiles.values()],
        }
        _print_json(data)
        return

    if args.cmd == "set-active":
        mgr.set_active(args.name)
        _print_json({"active": mgr.active_profile_name})
        return

    if args.cmd == "ping":
        _print_json(mgr.ping(args.name))
        return

    if args.cmd == "whoami":
        info = mgr.ping(args.name)
        _print_json({"profile": info.get("profile"), "user": info.get("user"), "connected": info.get("connected")})
        return

    if args.cmd == "set-password":
        mgr.set_built_in_credentials(args.name, args.username, args.password)
        print("stored")
        return

    if args.cmd == "clear-password":
        try:
            mgr.clear_built_in_credentials(args.name)
            print("cleared")
        except (PasswordDeleteError, KeyringError):
            # Already cleared or backend issue; keep output minimal
            print("cleared")
        return

    if args.cmd == "set-client-secret":
        mgr.set_oauth_client_secret(args.name, args.client_id, args.client_secret)
        print("stored")
        return

    if args.cmd == "clear-client-secret":
        try:
            mgr.clear_oauth_client_secret(args.name)
            print("cleared")
        except (PasswordDeleteError, KeyringError):
            print("cleared")
        return


if __name__ == "__main__":
    _cli()
