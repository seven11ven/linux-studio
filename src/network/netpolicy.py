"""Linux Studio network rules, shared by the proxy, the websites window and the tests.

Plain-language summary:
  * A "site" is one exact web address such as api.anthropic.com (no wildcards, no https://, no paths).
  * Sites are stored in ~/.config/linux-studio/network.json on your real computer. The sandbox can't see this file.
  * Only addresses on the public internet may be reached. Your own computer, your home network and
    cloud "metadata" addresses are always refused, whatever the list says.
Standard library only.
"""
import fcntl
import ipaddress
import json
import os
import re
import socket
import tempfile
from datetime import datetime, timezone

ALLOWED_PORT = 443  # HTTPS only (Project Manager decision)

# Addresses blocked from the start, without a pop-up (Project Manager decision, 2026-11-25).
# They show in the websites window as "Blocked (built in)"; allowing one there overrides this list.
BUILTIN_BLOCKED = {
    "redirector.gvt1.com": "Google: the editor engine's spellchecker dictionary downloads",
}


def effective_status(data, host):
    """'allowed', 'blocked' or None (unknown), taking the built-in block list into account."""
    status = data["sites"].get(host, {}).get("status")
    if status is None and host in BUILTIN_BLOCKED:
        return "blocked"
    return status

_LABEL = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
_HOST_RE = re.compile(rf"^(?=.{{1,253}}$){_LABEL}(?:\.{_LABEL})+$")


def normalise_host(raw):
    """Return the site name in canonical form, or None if it isn't a valid public host name.

    Refuses IP addresses, single-word names (like "localhost"), schemes, paths, ports and odd characters.
    """
    if not isinstance(raw, str):
        return None
    host = raw.strip().lower().rstrip(".")
    if not _HOST_RE.match(host):
        return None
    try:  # "1.2.3.4" matches the pattern above but is an IP address, not a name
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    # Old-style number forms such as "0x8.0x8.0x8.0x8", "1.0x1" or "127.1" are still IP addresses to the
    # system's address lookup (security review finding #2), so refuse anything it would read as a number.
    try:
        socket.inet_aton(host)
        return None
    except OSError:
        pass
    try:
        socket.getaddrinfo(host, None, flags=socket.AI_NUMERICHOST)
        return None
    except (OSError, UnicodeError):
        pass
    if host.split(".")[-1].isdigit():  # top-level part can't be all digits
        return None
    if host.endswith((".localhost", ".local", ".internal", ".home.arpa", ".lan")):
        return None
    return host


def is_public_ip(ip_text):
    """True only for addresses on the public internet (not private, loopback, link-local, reserved, multicast...)."""
    try:
        addr = ipaddress.ip_address(ip_text.split("%", 1)[0])
    except ValueError:
        return False
    # IPv6 addresses that wrap an IPv4 address: check the wrapped one (security review finding #6).
    if addr.version == 6:
        if addr.ipv4_mapped is not None:
            addr = addr.ipv4_mapped
        elif addr.sixtofour is not None:
            addr = addr.sixtofour
        elif addr.teredo is not None:
            addr = addr.teredo[1]
        elif addr in _NAT64_WELL_KNOWN or addr in _NAT64_LOCAL:
            addr = ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF)
    return addr.is_global and not addr.is_multicast


_NAT64_WELL_KNOWN = ipaddress.ip_network("64:ff9b::/96")
_NAT64_LOCAL = ipaddress.ip_network("64:ff9b:1::/48")


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    """Reads and safely writes network.json. Writes use a lock file and replace the whole file at once,
    so the proxy and the websites window never corrupt it."""

    def __init__(self, path):
        self.path = path
        self._cache = None
        self._mtime = None

    def _empty(self):
        return {"network_enabled": True, "sites": {}}

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return self._empty()
        except (OSError, ValueError):
            # A damaged file must never open the network: treat it as "network off".
            return {"network_enabled": False, "sites": {}, "_damaged": True}
        if not isinstance(data, dict):
            return {"network_enabled": False, "sites": {}, "_damaged": True}
        sites = {}
        for host, info in (data.get("sites") or {}).items():
            h = normalise_host(host)
            if h and isinstance(info, dict) and info.get("status") in ("allowed", "blocked"):
                sites[h] = {"status": info["status"], "last_used": str(info.get("last_used") or "")}
        return {"network_enabled": data.get("network_enabled") is True, "sites": sites}

    def load(self):
        """Current settings; re-reads the file only when it has changed."""
        try:
            mtime = os.stat(self.path).st_mtime_ns
        except FileNotFoundError:
            mtime = None
        if self._cache is None or mtime != self._mtime:
            self._cache = self._read()
            self._mtime = mtime
        return self._cache

    def update(self, change):
        """Apply change(data) under the lock and save atomically. Returns the saved data."""
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, mode=0o700, exist_ok=True)
        with open(self.path + ".lock", "a+") as lock:
            os.chmod(self.path + ".lock", 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = self._read()
            data.pop("_damaged", None)
            change(data)
            fd, tmp = tempfile.mkstemp(dir=directory, prefix=".network.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, sort_keys=True)
                    f.write("\n")
                os.chmod(tmp, 0o600)
                os.replace(tmp, self.path)
            except BaseException:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise
        self._cache = None
        return data

    def set_site(self, host, status):
        h = normalise_host(host)
        if not h or status not in ("allowed", "blocked"):
            raise ValueError("invalid site or status")

        def change(d):
            entry = d["sites"].setdefault(h, {"status": status, "last_used": ""})
            entry["status"] = status
        return self.update(change)

    def remove_site(self, host):
        h = normalise_host(host)
        return self.update(lambda d: d["sites"].pop(h, None))

    def set_network(self, enabled):
        def change(d):
            d["network_enabled"] = bool(enabled)
        return self.update(change)

    def touch(self, host):
        h = normalise_host(host)

        def change(d):
            if h in d["sites"]:
                d["sites"][h]["last_used"] = now_utc()
        return self.update(change)
