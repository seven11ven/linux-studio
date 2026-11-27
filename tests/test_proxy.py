#!/usr/bin/env python3
"""Unit tests for Linux Studio's network rules and proxy decisions (standard library only).
Run: python3 tests/test_proxy.py
"""
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "network"))
import studio_proxy  # noqa: E402
from netpolicy import Store, is_public_ip, normalise_host  # noqa: E402


class HostNames(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(normalise_host("API.Anthropic.com."), "api.anthropic.com")
        self.assertEqual(normalise_host("registry.npmjs.org"), "registry.npmjs.org")

    def test_invalid(self):
        for bad in ["", "localhost", "https://example.com", "example.com/path", "example.com:443",
                    "1.2.3.4", "[::1]", "exa mple.com", "-bad.com", "bad-.com", "a..com", "x" * 64 + ".com",
                    "printer.local", "nas.lan", "box.internal", "host.localhost", "example.123", None, 42,
                    "0x8.0x8.0x8.0x8", "1.0x1", "0x7f.0x1", "127.1", "0x7f000001"]:
            self.assertIsNone(normalise_host(bad), bad)


class Addresses(unittest.TestCase):
    def test_refused(self):
        for ip in ["127.0.0.1", "10.0.0.1", "172.16.5.4", "192.168.1.1", "169.254.169.254", "100.64.0.1",
                   "0.0.0.0", "224.0.0.1", "255.255.255.255", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1",
                   "::ffff:10.0.0.1", "2002:0a00:0001::1", "64:ff9b::7f00:1", "64:ff9b::a9fe:a9fe",
                   "64:ff9b:1::a00:1", "not-an-ip"]:
            self.assertFalse(is_public_ip(ip), ip)

    def test_public(self):
        for ip in ["93.184.215.14", "1.1.1.1", "2606:4700:4700::1111"]:
            self.assertTrue(is_public_ip(ip), ip)


class ConnectParsing(unittest.TestCase):
    def p(self, line):
        return studio_proxy.parse_connect(line.encode() + b"\r\nHost: x\r\n")

    def test_ok(self):
        self.assertEqual(self.p("CONNECT example.com:443 HTTP/1.1"), ("example.com", None))

    def test_refusals(self):
        self.assertEqual(self.p("GET http://example.com/ HTTP/1.1")[1], 405)
        self.assertEqual(self.p("CONNECT example.com:80 HTTP/1.1")[1], 403)
        self.assertEqual(self.p("CONNECT example.com:22 HTTP/1.1")[1], 403)
        self.assertEqual(self.p("CONNECT 127.0.0.1:443 HTTP/1.1")[1], 403)
        self.assertEqual(self.p("CONNECT 169.254.169.254:443 HTTP/1.1")[1], 403)
        self.assertEqual(self.p("CONNECT [::1]:443 HTTP/1.1")[1], 403)
        self.assertEqual(self.p("CONNECT localhost:443 HTTP/1.1")[1], 403)
        self.assertEqual(self.p("CONNECT example.com HTTP/1.1")[1], 400)
        self.assertEqual(self.p("garbage")[1], 400)
        self.assertEqual(self.p("CONNECT example.com:\u00b2 HTTP/1.1")[1], 400)     # superscript digit
        self.assertEqual(self.p("CONNECT example.com:0443 HTTP/1.1")[0], "example.com")
        self.assertEqual(self.p("CONNECT example.com:000000443 HTTP/1.1")[1], 400)


class Decisions(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "network.json")
        self.store = Store(self.path)
        self.env = {k: os.environ.pop(k) for k in ("DISPLAY", "WAYLAND_DISPLAY") if k in os.environ}

    def tearDown(self):
        os.environ.update(self.env)

    def write(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f)

    def test_empty_list_denies_headless(self):
        self.assertFalse(studio_proxy.Policy(self.store, "/nonexistent").allowed("example.com"))
        self.assertEqual(self.store.load()["sites"], {})          # headless deny is NOT saved

    def test_allowed_and_blocked(self):
        self.write({"network_enabled": True, "sites": {"a.com": {"status": "allowed"}, "b.com": {"status": "blocked"}}})
        p = studio_proxy.Policy(self.store, None)
        self.assertTrue(p.allowed("a.com"))
        self.assertFalse(p.allowed("b.com"))
        self.assertFalse(p.allowed("sub.a.com"))                 # exact address only

    def test_network_off(self):
        self.write({"network_enabled": False, "sites": {"a.com": {"status": "allowed"}}})
        self.assertFalse(studio_proxy.Policy(self.store, None).allowed("a.com"))

    def test_damaged_file_means_off(self):
        with open(self.path, "w") as f:
            f.write("{not json")
        self.assertFalse(studio_proxy.Policy(self.store, None).allowed("a.com"))

    def test_prompt_answers(self):
        p = studio_proxy.Policy(self.store, "x")
        p._has_display = lambda: True
        for code, expect_allow, expect_saved in [(11, True, None), (12, True, "allowed"), (10, False, "blocked")]:
            host = f"site{code}.com"

            class R:
                returncode = code
            orig = studio_proxy.subprocess.run
            studio_proxy.subprocess.run = lambda *a, **k: R()
            try:
                self.assertEqual(p.allowed(host), expect_allow)
            finally:
                studio_proxy.subprocess.run = orig
            self.assertEqual(self.store.load()["sites"].get(host, {}).get("status"), expect_saved)
        self.assertIn("site11.com", p.session_allowed)           # allow once = this session only

    def test_one_prompt_per_site(self):
        p = studio_proxy.Policy(self.store, "x")
        calls = []
        gate = threading.Event()

        def fake_ask(host):
            calls.append(host)
            gate.wait(2)
            p.session_allowed.add(host)   # what a real "Allow once" answer does
            return True
        p._ask = fake_ask
        results = []
        threads = [threading.Thread(target=lambda: results.append(p.allowed("x.com"))) for _ in range(5)]
        for t in threads:
            t.start()
        gate.set()
        for t in threads:
            t.join(5)
        self.assertEqual(calls, ["x.com"])
        self.assertEqual(results, [True] * 5)

    def _fake_prompt(self, p, code):
        class R:
            returncode = code
        p._has_display = lambda: True
        orig = studio_proxy.subprocess.run
        studio_proxy.subprocess.run = lambda *a, **k: R()
        return orig

    def test_closed_popup_denies_for_session(self):
        p = studio_proxy.Policy(self.store, "x")
        orig = self._fake_prompt(p, 1)                         # window closed
        try:
            self.assertFalse(p.allowed("a.com"))
            p._ask = lambda h: self.fail("asked again")        # must not ask again this session
            self.assertFalse(p.allowed("a.com"))
        finally:
            studio_proxy.subprocess.run = orig
        self.assertEqual(self.store.load()["sites"], {})       # not saved as blocked

    def test_block_all_new_sites(self):
        p = studio_proxy.Policy(self.store, "x")
        orig = self._fake_prompt(p, 13)
        try:
            self.assertFalse(p.allowed("a.com"))
            p._ask = lambda h: self.fail("asked after block-all")
            self.assertFalse(p.allowed("b.com"))
        finally:
            studio_proxy.subprocess.run = orig
        self.store.set_site("c.com", "allowed")
        self.assertTrue(p.allowed("c.com"))                    # already-approved sites still work

    def test_too_many_new_sites_refused(self):
        p = studio_proxy.Policy(self.store, "x")
        gate = threading.Event()
        p._ask = lambda h: gate.wait(3) and False
        threads = [threading.Thread(target=p.allowed, args=(f"s{i}.com",)) for i in range(studio_proxy.MAX_WAITING_SITES)]
        for t in threads:
            t.start()
        import time
        time.sleep(0.3)
        self.assertFalse(p.allowed("extra.com"))               # refused at once, no pop-up
        gate.set()
        for t in threads:
            t.join(5)

    def test_still_allowed_follows_changes(self):
        p = studio_proxy.Policy(self.store, None)
        self.store.set_site("a.com", "allowed")
        self.assertTrue(p.still_allowed("a.com"))
        self.store.set_site("a.com", "blocked")
        self.assertFalse(p.still_allowed("a.com"))
        self.store.set_site("a.com", "allowed")
        self.store.set_network(False)
        self.assertFalse(p.still_allowed("a.com"))

    def test_builtin_block_without_popup(self):
        p = studio_proxy.Policy(self.store, "x")
        p._ask = lambda h: self.fail("asked about a built-in blocked site")
        self.assertFalse(p.allowed("redirector.gvt1.com"))
        self.assertEqual(self.store.load()["sites"], {})       # nothing written
        self.store.set_site("redirector.gvt1.com", "allowed")   # user override in the websites window
        self.assertTrue(p.allowed("redirector.gvt1.com"))
        self.store.remove_site("redirector.gvt1.com")
        self.assertFalse(p.allowed("redirector.gvt1.com"))      # back to built-in block

    def _record_notices(self, p, answer=1):
        """Replace the notice program: record (site, kind) and answer with `answer`; run synchronously."""
        seen = []
        p.notice_path = "notice"
        p._has_display = lambda: True

        class R:
            returncode = answer
        orig_run, orig_thread = studio_proxy.subprocess.run, studio_proxy.threading.Thread

        def fake_run(cmd, **k):
            if cmd[1] == "notice":
                seen.append((cmd[2], cmd[3]))
            return R()

        class Now:                                  # run the notice "thread" straight away
            def __init__(self, target, daemon=None):
                self.t = target

            def start(self):
                self.t()
        studio_proxy.subprocess.run = fake_run
        studio_proxy.threading.Thread = Now
        return seen, (orig_run, orig_thread)

    def _restore(self, origs):
        studio_proxy.subprocess.run, studio_proxy.threading.Thread = origs

    def test_notice_once_for_a_site_you_blocked(self):
        self.write({"network_enabled": True, "sites": {"b.com": {"status": "blocked"}}})
        p = studio_proxy.Policy(self.store, None)
        seen, origs = self._record_notices(p)
        try:
            self.assertFalse(p.allowed("b.com"))
            self.assertFalse(p.allowed("b.com"))
        finally:
            self._restore(origs)
        self.assertEqual(seen, [("b.com", "blocked")])            # once per site per session

    def test_no_notice_for_builtin_blocks(self):
        p = studio_proxy.Policy(self.store, None)
        seen, origs = self._record_notices(p)
        try:
            self.assertFalse(p.allowed("redirector.gvt1.com"))
        finally:
            self._restore(origs)
        self.assertEqual(seen, [])

    def test_unanswered_notice_ask_now_asks_again(self):
        p = studio_proxy.Policy(self.store, "x")
        asked = []
        p._ask = lambda h: asked.append(h) or False
        p.session_denied.add("a.com")                            # an earlier pop-up went unanswered
        seen, origs = self._record_notices(p, answer=studio_proxy.NOTICE_ASK_NOW)
        try:
            self.assertFalse(p.allowed("a.com"))
        finally:
            self._restore(origs)
        self.assertEqual(seen, [("a.com", "unanswered")])
        self.assertEqual(asked, ["a.com"])                       # "Ask me now" showed the pop-up again

    def test_no_notice_while_a_popup_is_open(self):
        self.write({"network_enabled": True, "sites": {"b.com": {"status": "blocked"}}})
        p = studio_proxy.Policy(self.store, None)
        seen, origs = self._record_notices(p)
        try:
            with p.prompt_lock:                                  # an approval pop-up is on screen
                self.assertFalse(p.allowed("b.com"))
            self.assertEqual(seen, [])                           # never covers the pop-up
            self.assertFalse(p.allowed("b.com"))
        finally:
            self._restore(origs)
        self.assertEqual(seen, [("b.com", "blocked")])           # shown later instead

    def test_no_second_popup_after_a_deny(self):
        p = studio_proxy.Policy(self.store, "x")
        asked = []
        p._ask = lambda h: asked.append(h) or False
        self.store.set_site("a.com", "blocked")                  # an earlier pop-up just answered Deny
        p.pending.clear()
        # Simulate a connection that passed the first checks just before the answer was saved:
        with p.prompt_lock:
            pass
        self.assertFalse(p.allowed("a.com"))
        self.assertEqual(asked, [])

    def test_no_notice_without_display_or_program(self):
        self.write({"network_enabled": True, "sites": {"b.com": {"status": "blocked"}}})
        p = studio_proxy.Policy(self.store, None)                # no notice program given
        self.assertFalse(p.allowed("b.com"))
        self.assertEqual(p.notified, set())

    def test_store_writes_private_and_atomic(self):
        self.store.set_site("a.com", "allowed")
        self.assertEqual(oct(os.stat(self.path).st_mode & 0o777), "0o600")
        self.store.set_network(False)
        self.store.remove_site("a.com")
        data = json.load(open(self.path))
        self.assertEqual(data, {"network_enabled": False, "sites": {}})
        self.assertEqual([f for f in os.listdir(self.dir) if f.endswith(".tmp")], [])
        with self.assertRaises(ValueError):
            self.store.set_site("https://evil.com", "allowed")


class Inbox(unittest.TestCase):
    """Network inbox (PM decision 2026-11-27): new sites wait instead of a pop-up each."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "network.json")
        self.store = Store(self.path)
        self.status = os.path.join(self.tmp.name, "status")
        os.mkdir(self.status)
        self.p = studio_proxy.Policy(self.store, None, inbox_path="inbox", waiting_path="notice", status_dir=self.status)
        self.p._has_display = lambda: False          # no windows in tests

    def tearDown(self):
        self.tmp.cleanup()

    def count(self):
        with open(os.path.join(self.status, "pending")) as f:
            return int(f.read())

    def test_new_site_waits_and_is_refused(self):
        self.assertFalse(self.p.allowed("a.com"))
        self.assertFalse(self.p.allowed("a.com"))                 # listed once
        self.assertEqual([x["host"] for x in self.p.waiting_list()], ["a.com"])
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.store.load()["sites"], {})          # nothing saved until answered

    def test_answers(self):
        for h in ("a.com", "b.com", "c.com", "d.com"):
            self.p.allowed(h)
        self.p.answer("once a.com")
        self.assertTrue(self.p.allowed("a.com"))
        self.p.answer("always b.com")
        self.assertEqual(self.store.load()["sites"]["b.com"]["status"], "allowed")
        self.p.answer("deny c.com")
        self.assertEqual(self.store.load()["sites"]["c.com"]["status"], "blocked")
        self.assertEqual(self.count(), 1)
        self.p.answer("denyall")
        self.assertNotIn("d.com", self.store.load()["sites"])        # Deny all: until restart, not saved (N4)
        self.assertFalse(self.p.allowed("d.com"))
        self.assertEqual(self.count(), 0)

    def test_answers_only_for_waiting_sites(self):
        self.p.answer("always evil.com")                         # never asked: ignored
        self.p.answer("always ../etc")                           # not a site name: ignored
        self.assertEqual(self.store.load()["sites"], {})

    def test_cap(self):
        for i in range(studio_proxy.INBOX_MAX + 10):
            self.p.allowed(f"s{i}.example.com")
        self.assertEqual(len(self.p.waiting_list()), studio_proxy.INBOX_MAX)

    def test_expiry(self):
        self.p.allowed("a.com")
        wall, mono = self.p.waiting["a.com"]
        self.p.waiting["a.com"] = (wall, mono - studio_proxy.INBOX_EXPIRY - 1)   # expiry uses the monotonic clock
        self.p.expire()
        self.assertEqual(self.p.waiting_list(), [])
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.p.allowed("a.com"))               # asking again lists it again
        self.assertEqual(len(self.p.waiting_list()), 1)

    def test_open_requests_from_inside(self):
        opened = []
        self.p._spawn = lambda path, *a: (opened.append(a) if path == "inbox" else None) or None   # inbox only
        self.assertEqual(self.p.open_inbox(), "empty")              # nothing waiting: refused (N1)
        self.p.allowed("a.com")
        self.p.open_inbox()
        self.assertEqual(opened, [("--no-focus",)])                 # opened without keyboard focus (N1)
        self.assertEqual(self.p.open_inbox(), "too-soon")          # rate-limited
        self.p.open_inbox(from_user=True)                           # your own click: no limit, may take focus
        self.assertEqual(opened[-1], ())

    def test_open_inbox_is_not_raised_from_inside(self):
        class Alive:
            def poll(self):
                return None
        self.p.allowed("a.com")
        self.p.inbox_proc = Alive()
        self.p.inbox_proc.ls_queue = __import__("queue").Queue()
        self.p.last_inbox_open = -100
        self.assertEqual(self.p.open_inbox(), "already-open")
        self.assertTrue(self.p.inbox_proc.ls_queue.empty())        # no "show": not brought forward (N1)

    def test_deny_all_is_until_restart(self):
        for h in ("a.com", "b.com"):
            self.p.allowed(h)
        self.p.answer("denyall")
        self.assertEqual(self.store.load()["sites"], {})          # not saved (N4)
        self.assertFalse(self.p.allowed("a.com"))
        self.assertEqual(self.p.waiting_list(), [])                # and not listed again this session

    def test_block_new_sites(self):
        self.p.allowed("a.com")
        self.p.answer("blocknew")
        self.assertEqual(self.p.waiting_list(), [])
        self.assertFalse(self.p.allowed("z.com"))
        self.assertEqual(self.p.waiting_list(), [])                # new sites refused without being listed (N5)
        json.dump({"network_enabled": True, "sites": {"ok.com": {"status": "allowed"}}}, open(self.path, "w"))
        self.assertTrue(self.p.allowed("ok.com"))                  # approved sites keep working

    def test_settled_elsewhere_leaves_the_inbox(self):
        self.p.allowed("a.com")
        json.dump({"network_enabled": True, "sites": {"a.com": {"status": "allowed"}}}, open(self.path, "w"))
        self.assertTrue(self.p.allowed("a.com"))
        self.assertEqual(self.p.waiting_list(), [])                # N9
        self.assertEqual(self.count(), 0)

    def test_no_refused_notice_over_the_inbox(self):
        class Alive:
            def poll(self):
                return None
        json.dump({"network_enabled": True, "sites": {"b.com": {"status": "blocked"}}}, open(self.path, "w"))
        self.p.notice_path = "notice"
        self.p._has_display = lambda: True
        self.p.inbox_proc = Alive()
        self.p._notify("b.com", "blocked")
        self.assertEqual(self.p.notified, set())                   # N3

    def test_blocked_and_allowed_sites_skip_the_inbox(self):
        self.write = lambda d: json.dump(d, open(self.path, "w"))
        self.write({"network_enabled": True, "sites": {"x.com": {"status": "allowed"}, "y.com": {"status": "blocked"}}})
        self.assertTrue(self.p.allowed("x.com"))
        self.assertFalse(self.p.allowed("y.com"))
        self.assertEqual(self.p.waiting_list(), [])


class FixedList(unittest.TestCase):
    def test_only_listed_sites(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "sites.json")
        with open(f, "w") as fh:
            json.dump({"sites": ["nodejs.org", "Go.Dev.", "http://bad/", "1.2.3.4"]}, fh)
        p = studio_proxy.FixedPolicy(f)
        self.assertEqual(p.sites, {"nodejs.org", "go.dev"})
        self.assertTrue(p.allowed("nodejs.org"))
        self.assertFalse(p.allowed("example.com"))
        self.assertFalse(p.still_allowed("www.nodejs.org"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
