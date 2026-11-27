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
       studio_proxy.py --socket PATH --fixed-allowlist FILE [--parent-pid PID]
         (Toolchains explorer: only the sites in FILE, no pop-ups, nothing saved)
Standard library only.
"""
import argparse
import json
import queue
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
# Exit codes from refused_notice.py ("Connection refused" notice)
NOTICE_OPEN_SITES, NOTICE_ASK_NOW = 20, 21
NOTICE_TIMEOUT = 40          # the notice closes itself after 20 s; this is a safety margin
# Network inbox (PM decision 2026-11-27, mockup screen 8)
INBOX_EXPIRY = 600           # a request nobody answers disappears after 10 minutes
INBOX_MAX = 50               # at most this many sites wait at once; more are refused without being listed
INBOX_OPEN_INTERVAL = 3      # "open the inbox" requests from inside Linux Studio: at most one per 3 seconds
INBOX_REQUEST = b"LINUX-STUDIO-INBOX "   # what the editor's status-bar item sends to ask for the inbox


class Policy:
    def __init__(self, store, prompt_path, notice_path=None, launcher=None,
                 inbox_path=None, waiting_path=None, status_dir=None):
        self.store = store
        self.prompt_path = prompt_path
        # Network inbox: when inbox_path is set, new sites wait in the inbox instead of getting a pop-up each.
        self.inbox_path = inbox_path         # the inbox window (network_inbox.py)
        self.waiting_path = waiting_path     # the small "N websites are waiting" notice (waiting_notice.py)
        self.status_dir = status_dir         # count for the editor's status bar (read-only inside the sandbox)
        self.waiting = {}                    # host -> (wall time first asked, monotonic time for expiry)
        self.seen_ever = set()               # every site that has waited this session (N5: "Later" handling)
        self.inbox_proc = None
        self.waiting_proc = None
        self.waiting_later = False           # "Later" pressed: no notice until a new site arrives
        self.last_inbox_open = 0.0
        self.ui_lock = threading.Lock()      # starting the notice / inbox: never two at once
        self.notice_path = notice_path   # "Connection refused" notice (PM decision 2026-11-26)
        self.launcher = launcher         # used by the notice's "Open Approved websites…"
        self.notified = set()            # sites already noticed this session (at most once per site)
        self.notice_busy = False         # one notice on screen at a time
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

    def _notify(self, host, kind):
        """Show the "Connection refused" notice for a site refused without a pop-up: kind is "blocked" (you blocked
        it) or "unanswered" (an earlier pop-up was closed or not answered). Once per site per session, one at a time,
        never blocks the connection that triggered it."""
        if not self.notice_path or not self._has_display():
            return
        if self.prompt_lock.locked() or self._alive(self.inbox_proc):
            return   # an approval pop-up or the inbox is open: never cover it (F3, N3); maybe next time
        with self.lock:
            if host in self.notified or self.notice_busy:
                return
            self.notified.add(host)
            self.notice_busy = True

        def run():
            try:
                code = subprocess.run([sys.executable, self.notice_path, host, kind], timeout=NOTICE_TIMEOUT,
                                      check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
            except (subprocess.TimeoutExpired, OSError):
                code = None
            finally:
                with self.lock:
                    self.notice_busy = False
            if code == NOTICE_OPEN_SITES and kind == "blocked" and self.launcher:
                try:
                    subprocess.Popen([self.launcher, "--network-highlight", host], start_new_session=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except OSError:
                    pass
            elif code == NOTICE_ASK_NOW and kind == "unanswered":
                with self.lock:
                    self.session_denied.discard(host)
                self.allowed(host)        # shows the approval pop-up now; its answer applies to the next connection
        threading.Thread(target=run, daemon=True).start()

    def allowed(self, host):
        data = self.store.load()
        if not data["network_enabled"]:
            return False
        status = effective_status(data, host)
        if status == "blocked":
            if self.inbox_path and host in self.waiting:
                self._settle(host)           # blocked in Approved websites meanwhile (N9)
            if host in data["sites"]:      # blocked by you (built-in blocks stay silent, as decided)
                self._notify(host, "blocked")
            return False
        if status == "allowed" or host in self.session_allowed:
            if self.inbox_path and host in self.waiting:
                self._settle(host)           # allowed in Approved websites meanwhile (N9)
            return True
        if self.inbox_path:
            if self.block_new or host in self.session_denied:
                return False                 # "Block new sites until restart" / "Deny all": refused, not listed
            # Unknown site: it waits in the inbox (refused until answered there).
            self._enqueue(host)
            return False
        # Unknown site: one pop-up per site, other requests for it wait for the same answer.
        with self.lock:
            # Re-check: an answer may have arrived while we were waiting for the lock.
            if host in self.session_allowed:
                return True
            status = effective_status(self.store.load(), host)
            if status in ("allowed", "blocked"):
                return status == "allowed" and self.store.load()["network_enabled"]
            if self.block_new:
                return False
            denied_unanswered = host in self.session_denied
        if denied_unanswered:
            self._notify(host, "unanswered")
            return False
        with self.lock:
            if host in self.session_allowed:
                return True
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
                    # Re-check everything now: an earlier pop-up may have just answered for this site (F4).
                    status = effective_status(self.store.load(), host)
                    if status == "allowed" or host in self.session_allowed:
                        result[0] = True
                    elif status == "blocked" or self.block_new or host in self.session_denied:
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

    # ---------- network inbox ----------
    # Security review 2026-11-27 (PM-approved fixes N1-N10): code inside Linux Studio can't answer or see the inbox;
    # these rules also stop it from choosing *when* the inbox or a notice appears to trick a reflex "Allow".
    def _enqueue(self, host):
        with self.lock:
            self._expire_locked()
            if host in self.waiting or len(self.waiting) >= INBOX_MAX:
                return
            self.waiting[host] = (time.time(), time.monotonic())   # (shown to you, used for expiry: N10)
            if host not in self.seen_ever:
                self.seen_ever.add(host)
                self.waiting_later = False   # only a genuinely new site brings the notice back after "Later" (N5)
        self._publish()

    def _expire_locked(self):
        now = time.monotonic()
        old = [h for h, (_wall, mono) in self.waiting.items() if now - mono >= INBOX_EXPIRY]
        for h in old:
            del self.waiting[h]
        return bool(old)

    def expire(self):
        with self.lock:
            changed = self._expire_locked()
        if changed:
            self._publish()

    def _settle(self, host):
        """A waiting site that was allowed or blocked elsewhere (Approved websites) leaves the inbox (N9)."""
        with self.lock:
            gone = self.waiting.pop(host, None) is not None
        if gone:
            self._publish()

    def waiting_list(self):
        with self.lock:
            now_mono = time.monotonic()
            return [{"host": h, "since": int(wall), "expires": int(time.time() + max(0, INBOX_EXPIRY - (now_mono - mono)))}
                    for h, (wall, mono) in sorted(self.waiting.items(), key=lambda x: x[1][1])]

    def _publish(self):
        """Tell everyone the inbox changed: the status file (editor), the notice and an open inbox window. The
        snapshot and the file write happen under ui_lock, so an older snapshot can never land last (N6)."""
        with self.ui_lock:
            sites = self.waiting_list()
            count = len(sites)
            if self.status_dir:
                try:
                    tmp = os.path.join(self.status_dir, ".pending.tmp")
                    with open(tmp, "w", encoding="utf-8") as f:
                        f.write(f"{count}\n")
                    os.replace(tmp, os.path.join(self.status_dir, "pending"))
                except OSError:
                    pass
            self._send(self.inbox_proc, json.dumps({"sites": sites}))
            if count == 0:
                self._send(self.waiting_proc, "count 0")
            elif self._alive(self.waiting_proc):
                self._send(self.waiting_proc, f"count {count}")
            elif not self.waiting_later and not self._alive(self.inbox_proc):
                self._start_waiting_notice(count)

    @staticmethod
    def _alive(proc):
        return proc is not None and proc.poll() is None

    def _send(self, proc, line):
        """Queue a line for a child window. Each child has its own writer thread, so a child that stops reading can
        never stall the proxy (N7)."""
        if not self._alive(proc):
            return
        q = getattr(proc, "ls_queue", None)
        if q is not None:
            try:
                q.put_nowait(line)
            except queue.Full:
                pass     # the child isn't reading; drop rather than block

    def _spawn(self, path, *args):
        if not path or not self._has_display():
            return None
        try:
            proc = subprocess.Popen([sys.executable, path, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True, bufsize=1)
        except OSError:
            return None
        proc.ls_queue = queue.Queue(maxsize=64)

        def writer():
            while proc.poll() is None:
                try:
                    line = proc.ls_queue.get(timeout=1)
                except queue.Empty:
                    continue
                try:
                    proc.stdin.write(line + "\n")
                    proc.stdin.flush()
                except (OSError, ValueError):
                    return
        threading.Thread(target=writer, daemon=True).start()
        return proc

    def _start_waiting_notice(self, count):
        proc = self._spawn(self.waiting_path, str(count))
        if proc is None:
            return
        self.waiting_proc = proc

        def read():
            last = ""
            for line in proc.stdout:
                last = line.strip()
                if last == "open":
                    self.open_inbox(from_user=True)
            proc.wait()
            # Closed with "Later" or the window's X: stay hidden until a genuinely new site arrives (N5).
            if last != "open":
                with self.lock:
                    if self.waiting:
                        self.waiting_later = True
        threading.Thread(target=read, daemon=True).start()

    def open_inbox(self, from_user=False):
        """Show the inbox window. from_user=True is your own click on the notice's "Open inbox": the window may take
        the keyboard. Anything arriving through the proxy socket (the editor's status-bar item, Settings, or any code
        inside Linux Studio) is treated with suspicion (N1): refused while nothing is waiting, rate-limited, never
        raises an inbox that is already open, and opens it without keyboard focus (you click it first).
        Returns "opened", "already-open", "empty" or "too-soon"."""
        with self.ui_lock:
            return self._open_inbox_locked(from_user)

    def _open_inbox_locked(self, from_user):
        if not from_user:
            with self.lock:
                if not self.waiting:
                    return "empty"
            now = time.monotonic()
            if now - self.last_inbox_open < INBOX_OPEN_INTERVAL:
                return "too-soon"
            self.last_inbox_open = now
            if self._alive(self.inbox_proc):
                return "already-open"
        elif self._alive(self.inbox_proc):
            self._send(self.inbox_proc, "show")
            return "already-open"
        proc = self._spawn(self.inbox_path, *([] if from_user else ["--no-focus"]))
        if proc is None:
            return "empty"
        self.inbox_proc = proc
        self._send(self.waiting_proc, "count 0")    # the inbox replaces the small notice
        self._send(proc, json.dumps({"sites": self.waiting_list()}))

        def read():
            for line in proc.stdout:
                self.answer(line.strip())
            proc.wait()
        threading.Thread(target=read, daemon=True).start()
        return "opened"

    def answer(self, line):
        """Apply one answer from the inbox window: "deny HOST", "once HOST", "always HOST", "denyall" (refused until
        Linux Studio restarts, not saved: N4) or "blocknew" (refuse every new site until restart: N5)."""
        verb, _, rest = line.partition(" ")
        if verb == "blocknew":
            with self.lock:
                self.block_new = True
                hosts = list(self.waiting)
                self.waiting.clear()
                self.session_denied.update(hosts)
            self._publish()
            return
        with self.lock:
            if verb == "denyall":
                hosts = list(self.waiting)
            else:
                host = normalise_host(rest)
                hosts = [host] if host and host in self.waiting else []   # only sites actually waiting
            for h in hosts:
                del self.waiting[h]
        data = self.store.load()
        for h in hosts:
            if effective_status(data, h) in ("allowed", "blocked") and verb in ("deny", "denyall"):
                continue          # settled meanwhile in Approved websites: don't overrule it (N9)
            if verb == "deny":
                self.store.set_site(h, "blocked")
            elif verb == "denyall":
                self.session_denied.add(h)
            elif verb == "once":
                self.session_allowed.add(h)
            elif verb == "always":
                self.store.set_site(h, "allowed")
        if hosts:
            self._publish()

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


class FixedPolicy:
    """Only the sites listed in a fixed file (official download sites). No pop-ups, nothing written."""

    def __init__(self, path):
        import json
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.sites = {h for h in (normalise_host(x) for x in data.get("sites", [])) if h}

    def allowed(self, host):
        return host in self.sites

    def still_allowed(self, host):
        return host in self.sites

    def touch(self, host):
        pass


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


REASONS = {200: "OK", 404: "Not Found", 429: "Too Many Requests", 400: "Bad Request", 403: "Forbidden", 405: "Method Not Allowed", 502: "Bad Gateway", 503: "Service Unavailable"}


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
        policy = self.server.policy
        if head.startswith(INBOX_REQUEST) and hasattr(policy, "open_inbox") and getattr(policy, "inbox_path", None):
            # The editor's status-bar item asks for the inbox (it can't answer anything itself; rate-limited).
            result = policy.open_inbox(from_user=False)
            self._reply({"opened": 200, "already-open": 200, "empty": 404, "too-soon": 429}.get(result, 404))
            return
        host, err = parse_connect(head)
        if err:
            self._reply(err)
            return
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
    ap.add_argument("--config")
    ap.add_argument("--fixed-allowlist")
    ap.add_argument("--prompt")
    ap.add_argument("--notice", help="the \"Connection refused\" notice program")
    ap.add_argument("--launcher", help="the linux-studio launcher (for \"Open Approved websites\")")
    ap.add_argument("--inbox", help="the network inbox window (new sites wait there instead of a pop-up each)")
    ap.add_argument("--waiting-notice", help="the small \"N websites are waiting\" notice")
    ap.add_argument("--status-dir", help="folder for the waiting count the editor shows (read-only inside the sandbox)")
    ap.add_argument("--parent-pid", type=int)
    args = ap.parse_args()
    if bool(args.config) == bool(args.fixed_allowlist):
        ap.error("use exactly one of --config or --fixed-allowlist")

    old_umask = os.umask(0o177)              # socket readable/writable by you only
    server = Server(args.socket, Handler)
    os.umask(old_umask)
    server.policy = (FixedPolicy(args.fixed_allowlist) if args.fixed_allowlist
                     else Policy(Store(args.config), args.prompt, args.notice, args.launcher,
                                 args.inbox, args.waiting_notice, args.status_dir))
    server.slots = threading.BoundedSemaphore(MAX_TUNNELS)

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    if getattr(server.policy, "inbox_path", None):    # expire unanswered inbox requests
        def expire_loop():
            while True:
                time.sleep(15)
                server.policy.expire()
        threading.Thread(target=expire_loop, daemon=True).start()
        server.policy._publish()                     # start with an empty count file

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
