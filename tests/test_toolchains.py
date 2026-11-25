#!/usr/bin/env python3
"""Offline unit tests for the Toolchains worker's safety checks (no network needed).
Run: python3 tests/test_toolchains.py      (needs gpgv for the signature tests; they're skipped without it)
"""
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src", "toolchains"))
import worker  # noqa: E402


def make_tar(path, entries):
    """entries: list of (name, kind, data_or_target). kind: file | dir | symlink | hardlink | dev"""
    with tarfile.open(path, "w:gz") as tar:
        for name, kind, extra in entries:
            ti = tarfile.TarInfo(name)
            if kind == "file":
                data = extra.encode()
                ti.size = len(data)
                tar.addfile(ti, io.BytesIO(data))
                continue
            ti.type = {"dir": tarfile.DIRTYPE, "symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE,
                       "dev": tarfile.CHRTYPE}[kind]
            if kind in ("symlink", "hardlink"):
                ti.linkname = extra
            tar.addfile(ti)


class Sandboxed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "toolchains")
        os.makedirs(self.root)
        worker.ROOT, worker.STAGING = self.root, os.path.join(self.root, ".staging")
        self.sent = []
        worker.send = lambda **m: self.sent.append(m)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Checksums(unittest.TestCase):
    def test_lookup(self):
        text = "a" * 64 + "  node-v1-linux-x64.tar.xz\n" + "b" * 64 + "  other.tar.gz\n"
        self.assertEqual(worker.checksum_from_file(text, "node-v1-linux-x64.tar.xz"), "a" * 64)
        with self.assertRaises(worker.Fail):
            worker.checksum_from_file(text, "missing.tar.gz")
        with self.assertRaises(worker.Fail):
            worker.checksum_from_file("nothex  file.tar.gz", "file.tar.gz")

    def test_require_sha(self):
        worker.require_sha("ab" * 32, "AB" * 32)
        for bad in ["cd" * 32, "", None]:
            with self.assertRaises(worker.Fail):
                worker.require_sha("ab" * 32, bad)

    def test_https_only(self):
        with self.assertRaises(worker.Fail):
            worker._open("http://nodejs.org/dist/index.json")


class Extraction(Sandboxed):
    def check_refused(self, entries):
        arc = os.path.join(self.tmp, "a.tar.gz")
        make_tar(arc, entries)
        dest = os.path.join(self.tmp, "out")
        os.makedirs(dest, exist_ok=True)
        with self.assertRaises(worker.Fail):
            worker.safe_extract(arc, dest)

    def test_parent_path(self):
        self.check_refused([("../escape.txt", "file", "x")])

    def test_absolute_path(self):
        self.check_refused([("/tmp/abs.txt", "file", "x")])

    def test_symlink_escape(self):
        self.check_refused([("pkg/link", "symlink", "/etc/passwd")])
        self.check_refused([("pkg/link", "symlink", "../../outside")])

    def test_hardlink_escape(self):
        self.check_refused([("pkg/hl", "hardlink", "/etc/passwd")])

    def test_device_file(self):
        self.check_refused([("pkg/dev", "dev", None)])

    def test_good_archive_and_top_dir(self):
        arc = os.path.join(self.tmp, "ok.tar.gz")
        make_tar(arc, [("tool-1.0/", "dir", None), ("tool-1.0/bin/", "dir", None), ("tool-1.0/bin/tool", "file", "#!/bin/sh\n"),
                       ("tool-1.0/bin/alias", "symlink", "tool")])
        dest = os.path.join(self.tmp, "out")
        os.makedirs(dest)
        worker.safe_extract(arc, dest)
        top = worker.single_top_dir(dest)
        self.assertTrue(top.endswith("tool-1.0"))
        self.assertTrue(os.path.isfile(os.path.join(top, "bin", "tool")))

    def test_too_many_entries(self):
        old = worker.MAX_ENTRIES
        worker.MAX_ENTRIES = 2
        try:
            self.check_refused([("a", "file", "1"), ("b", "file", "2"), ("c", "file", "3")])
        finally:
            worker.MAX_ENTRIES = old

    def test_too_large(self):
        old = worker.MAX_UNPACKED
        worker.MAX_UNPACKED = 5
        try:
            self.check_refused([("big.txt", "file", "123456789")])
        finally:
            worker.MAX_UNPACKED = old


class InstallFlow(Sandboxed):
    def fake_publisher(self, files, fail=None):
        def install(version, work, progress):
            if fail:
                raise worker.Fail(fail)
            arc = os.path.join(work, "t.tar.gz")
            make_tar(arc, files)
            return arc
        worker.PUBLISHERS["node"] = (lambda: [], install)

    def test_success_then_use_and_remove(self):
        self.fake_publisher([("n/", "dir", None), ("n/bin/", "dir", None), ("n/bin/node", "file", "x")])
        worker.install("node", "26.13.1")
        self.assertTrue(os.path.isfile(os.path.join(self.root, "node", "26.13.1", "bin", "node")))
        self.assertEqual(os.listdir(worker.STAGING), [])                   # staging cleaned
        worker.use("node", "26.13.1")
        self.assertEqual(os.readlink(os.path.join(self.root, "node", "current")), "26.13.1")   # relative link
        self.assertEqual(worker.installed(), [{"tool": "node", "version": "26.13.1", "current": True}])
        worker.remove("node", "26.13.1")
        self.assertFalse(os.path.lexists(os.path.join(self.root, "node", "current")))
        self.assertEqual(worker.installed(), [])

    def test_failed_verification_leaves_nothing(self):
        self.fake_publisher([], fail="The publisher's signature didn't match")
        with self.assertRaises(worker.Fail):
            worker.install("node", "26.13.1")
        self.assertFalse(os.path.exists(os.path.join(self.root, "node", "26.13.1")))
        self.assertEqual(os.listdir(worker.STAGING), [])

    def test_wrong_layout_refused(self):
        self.fake_publisher([("readme.txt", "file", "no bin folder")])
        with self.assertRaises(worker.Fail):
            worker.install("node", "26.13.1")
        self.assertFalse(os.path.exists(os.path.join(self.root, "node", "26.13.1")))

    def test_bad_names_refused(self):
        for tool, version in [("evil", "1.0"), ("node", "../../etc"), ("node", "1.0/x"), ("node", ""), ("node", "a" * 50)]:
            with self.assertRaises(worker.Fail):
                worker.install(tool, version)

    def test_tampered_tool_folder_refused(self):
        os.symlink("/", os.path.join(self.root, "node"))
        with self.assertRaises(worker.Fail):
            worker.use("node", "1.0")


@unittest.skipUnless(shutil.which("gpgv") and shutil.which("gpg"), "gpg/gpgv not installed")
class Signatures(unittest.TestCase):
    def test_good_and_bad(self):
        tmp = tempfile.mkdtemp()
        try:
            home = os.path.join(tmp, "gnupg")
            os.makedirs(home, mode=0o700)
            env = dict(os.environ, GNUPGHOME=home)
            subprocess.run(["gpg", "--batch", "--passphrase", "", "--quick-gen-key", "Test <t@example.invalid>",
                            "ed25519", "sign", "1d"], env=env, check=True, capture_output=True)
            keys = os.path.join(tmp, "keys")
            os.makedirs(keys)
            with open(os.path.join(keys, "test.gpg"), "wb") as f:
                f.write(subprocess.run(["gpg", "--export"], env=env, check=True, capture_output=True).stdout)
            data = os.path.join(tmp, "SHASUMS256.txt")
            with open(data, "w") as f:
                f.write("a" * 64 + "  file.tar.gz\n")
            subprocess.run(["gpg", "--batch", "--detach-sign", "-o", data + ".sig", data], env=env, check=True,
                           capture_output=True)
            fpr = [l.split(":")[9] for l in subprocess.run(["gpg", "--with-colons", "--list-keys"], env=env, check=True,
                   capture_output=True, text=True).stdout.splitlines() if l.startswith("fpr")][0]
            import json as _j
            with open(os.path.join(keys, "allowed-signers.json"), "w") as f:
                _j.dump({"test.gpg": []}, f)
            worker.KEYS = keys
            with self.assertRaises(worker.Fail):                              # valid signature, key not allow-listed
                worker.verify_signature("test.gpg", data + ".sig", data)
            with open(os.path.join(keys, "allowed-signers.json"), "w") as f:
                _j.dump({"test.gpg": [fpr]}, f)
            worker.verify_signature("test.gpg", data + ".sig", data)          # good
            with open(data, "a") as f:
                f.write("tampered\n")
            with self.assertRaises(worker.Fail):
                worker.verify_signature("test.gpg", data + ".sig", data)      # tampered
            with open(os.path.join(keys, "other.gpg"), "wb") as f:
                f.write(b"")
            with self.assertRaises(worker.Fail):
                worker.verify_signature("other.gpg", data + ".sig", data)     # wrong key
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=1)
