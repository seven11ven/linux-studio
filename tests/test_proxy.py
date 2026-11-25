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


if __name__ == "__main__":
    unittest.main(verbosity=1)
