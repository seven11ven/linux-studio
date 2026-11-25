#!/usr/bin/python3
"""Linux Studio approved-websites proxy (runs on your real computer, one per Linux Studio launch).

The sandbox has no network of its own. Its only way out is this proxy, reached through a unix socket.
For every connection the proxy:
  1. accepts only "CONNECT <site>:443" (HTTPS). Anything else is refused.
  2. checks network.json: network off, or site blocked, means refuse. Site allowed means continue.
     An unknown site opens the approval pop-up; no answer, or no screen, means refuse.
  3. looks up the site's address itself and refuses private, loopback, link-local and reserved addresses,
     so the sandbox can never reach your computer, your home network or cloud metadata services.
  4. passes the encrypted bytes through without reading them, and logs nothing about the traffic.

Usage: studio_proxy.py --socket PATH --config PATH [--prompt PATH] [--parent-pid PID]
Standard library only.
"""
import argparse
import os
import select
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from netpolicy import ALLOWED_PORT, Store, effective_status, is_public_ip, normalise_host  # noqa: E402

HEADER_LIMIT = 8192        # bytes allowed in the CONNECT request
HEADER_TIMEOUT = 10        # seconds to send the request
CONNECT_TIMEOUT = 10       # seconds to reach the website
IDLE_TIMEOUT = 300         # close tunnels idle for 5 minutes
PROMPT_TIMEOUT = 60        # no answer in 60 s = deny
MAX_TUNNELS = 64           # simultaneous connections
TOUCH_INTERVAL = 60        # update "last used" at most once a minute per site
MAX_WAITING_SITES = 3      # more new sites than this waiting for a pop-up are refused at once
DNS_TIMEOUT = 10           # seconds to look up a site's address
RECHECK_INTERVAL = 5       # open tunnels re-check the rules this often (closed if blocked / network off)
SEND_TIMEOUT = 30          # a side that stops reading for this long ends the tunnel

# Exit codes from approval_prompt.py
PROMPT_DENY, PROMPT_ONCE, PROMPT_ALWAYS, PROMPT_BLOCK_NEW = 10, 11, 12, 13


class Policy:
    def __init__(self, store, prompt_path):
        self.store = store
        self.prompt_path = prompt_path
        self.session_allowed = set()
        self.session_denied = set()  # closed / timed-out pop-ups: refused until Linux Studio restarts
        self.block_new = False       # "Block all new sites until restart"
        self.pending = {}            # host -> (Event, result list)
        self.lock = threading.Lock()
        self.prompt_lock = threading.Lock()   # only one pop-up on screen at a time
        self.last_touch = {}

    def _has_display(self):
        return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))

    def _ask(self, host):
        """Run the pop-up. Returns True to allow this connection."""
        if not self.prompt_path or not self._has_display():
            return False
        try:
            code = subprocess.run([sys.executable, self.prompt_path, host, str(ALLOWED_PORT)],
                                  timeout=PROMPT_TIMEOUT, check=False,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
        except (subprocess.TimeoutExpired, OSError):
            code = None
        if code == PROMPT_BLOCK_NEW:
            self.block_new = True
            return False
        if code == PROMPT_ALWAYS:
            self.store.set_site(host, "allowed")
            return True
        if code == PROMPT_ONCE:
            self.session_allowed.add(host)
            return True
        if code == PROMPT_DENY:
            self.store.set_site(host, "blocked")   # stays listed, refused silently next time
            return False
        self.session_denied.add(host)              # closed or no answer: don't ask again this session
        return False

    def allowed(self, host):
        data = self.store.load()
        if not data["network_enabled"]:
            return False
        status = effective_status(data, host)
        if status == "blocked":
            return False
        if status == "allowed" or host in self.session_allowed:
            return True
        # Unknown site: one pop-up per site, other requests for it wait for the same answer.
        with self.lock:
            # Re-check: an answer may have arrived while we were waiting for the lock.
            if host in self.session_allowed:
                return True
            status = effective_status(self.store.load(), host)
            if status in ("allowed", "blocked"):
                return status == "allowed" and self.store.load()["network_enabled"]
            if self.block_new or host in self.session_denied:
                return False
            entry = self.pending.get(host)
            owner = entry is None
            if owner and len(self.pending) >= MAX_WAITING_SITES:
                return False                       # too many new sites at once: refuse, no pop-up
            if owner:
                entry = (threading.Event(), [False])
                self.pending[host] = entry
        event, result = entry
        if owner:
            try:
                with self.prompt_lock:             # wait for any other pop-up to be answered first
                    if self.block_new or host in self.session_denied:
                        result[0] = False
                    else:
                        result[0] = self._ask(host)
            finally:
                with self.lock:
                    self.pending.pop(host, None)
                event.set()
        else:
            event.wait(PROMPT_TIMEOUT * (MAX_WAITING_SITES + 1))
        return result[0] and self.store.load()["network_enabled"]

    def still_allowed(self, host):
        """Used by open tunnels: False once the site is blocked/removed or the network is turned off."""
        data = self.store.load()
        if not data["network_enabled"]:
            return False
        status = effective_status(data, host)
        return status == "allowed" or (status is None and host in self.session_allowed)

    def touch(self, host):
        now = time.monotonic()
        if now - self.last_touch.get(host, 0) >= TOUCH_INTERVAL:
            self.last_touch[host] = now
            try:
                self.store.touch(host)
            except OSError:
                pass


def _lookup(host, box):
    try:
        box.append(socket.getaddrinfo(host, ALLOWED_PORT, type=socket.SOCK_STREAM))
    except (OSError, UnicodeError):
        box.append([])


def resolve_public(host):
    """Public addresses for host, or [] if ANY address is non-public (mixed answers are refused).
    The lookup has a time limit so a slow name server can't hold a connection slot forever."""
    box = []
    t = threading.Thread(target=_lookup, args=(host, box), daemon=True)
    t.start()
    t.join(DNS_TIMEOUT)
    infos = box[0] if box else []
    addrs = [(fam, sa) for fam, _, _, _, sa in infos]
    if not addrs or not all(is_public_ip(sa[0]) for _, sa in addrs):
        return []
    return addrs


def parse_connect(head):
    """Parse the request head. Returns (host, error_status)."""
    try:
        text = head.decode("latin-1")
    except UnicodeDecodeError:
        return None, 400
    line = text.split("\r\n", 1)[0]
    parts = line.split(" ")
    if len(parts) != 3 or not parts[2].startswith("HTTP/1."):
        return None, 400
    method, target, _ = parts
    if method != "CONNECT":
        return None, 405
    if target.startswith("["):          # IPv6 literal
        return None, 403
    host, sep, port = target.rpartition(":")
    if not sep or not (port.isascii() and port.isdigit()) or len(port) > 5:
        return None, 400
    if int(port) != ALLOWED_PORT:
        return None, 403
    clean = normalise_host(host)
    if not clean:
        return None, 403
    return clean, None


REASONS = {400: "Bad Request", 403: "Forbidden", 405: "Method Not Allowed", 502: "Bad Gateway", 503: "Service Unavailable"}


class Handler(socketserver.BaseRequestHandler):
    def _reply(self, status):
        try:
            self.request.sendall(f"HTTP/1.1 {status} {REASONS.get(status, 'Error')}\r\nContent-Length: 0\r\n"
                                 "Connection: close\r\n\r\n".encode())
        except OSError:
            pass

    def _read_head(self):
        deadline = time.monotonic() + HEADER_TIMEOUT   # one overall limit, not per read
        buf = b""
        while b"\r\n\r\n" not in buf:
            if len(buf) > HEADER_LIMIT:
                return None
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            self.request.settimeout(left)
            chunk = self.request.recv(4096)
            if not chunk:
                return None
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        return head, rest

    def handle(self):
        server = self.server
        if not server.slots.acquire(blocking=False):
            self._reply(503)
            return
        try:
            self._handle()
        finally:
            server.slots.release()

    def _handle(self):
        try:
            got = self._read_head()
        except OSError:
            return
        if got is None:
            self._reply(400)
            return
        head, early = got
        host, err = parse_connect(head)
        if err:
            self._reply(err)
            return
        policy = self.server.policy
        if not policy.allowed(host):
            self._reply(403)
            return
        addrs = resolve_public(host)
        if not addrs:
            self._reply(403)
            return
        upstream = None
        for fam, sa in addrs:
            try:
                upstream = socket.socket(fam, socket.SOCK_STREAM)
                upstream.settimeout(CONNECT_TIMEOUT)
                upstream.connect(sa)      # connect to the exact address we checked
                break
            except OSError:
                upstream.close()
                upstream = None
        if upstream is None:
            self._reply(502)
            return
        policy.touch(host)
        try:
            self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            if early:
                upstream.sendall(early)
            pipe(self.request, upstream, lambda: policy.still_allowed(host))
        except OSError:
            pass
        finally:
            upstream.close()


def pipe(a, b, still_ok=lambda: True):
    """Copy bytes both ways until either side closes, the tunnel is idle too long,
    or the site stops being allowed (blocked, removed, or network turned off)."""
    a.settimeout(SEND_TIMEOUT)
    b.settimeout(SEND_TIMEOUT)
    socks = [a, b]
    last_activity = time.monotonic()
    while True:
        ready, _, _ = select.select(socks, [], [], RECHECK_INTERVAL)
        if not still_ok():
            return
        if not ready:
            if time.monotonic() - last_activity > IDLE_TIMEOUT:
                return
            continue
        last_activity = time.monotonic()
        for s in ready:
            data = s.recv(65536)
            if not data:
                return
            (b if s is a else a).sendall(data)


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False

    def handle_error(self, request, client_address):
        pass   # never print request details (privacy; security review finding #7)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--socket", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--prompt")
    ap.add_argument("--parent-pid", type=int)
    args = ap.parse_args()

    old_umask = os.umask(0o177)              # socket readable/writable by you only
    server = Server(args.socket, Handler)
    os.umask(old_umask)
    server.policy = Policy(Store(args.config), args.prompt)
    server.slots = threading.BoundedSemaphore(MAX_TUNNELS)

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    if args.parent_pid:                      # exit if the launcher disappears
        def watch():
            while True:
                time.sleep(2)
                try:
                    os.kill(args.parent_pid, 0)
                except ProcessLookupError:
                    stop()
                    return
        threading.Thread(target=watch, daemon=True).start()

    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        try:
            os.unlink(args.socket)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
