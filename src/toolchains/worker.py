#!/usr/bin/env python3
"""Linux Studio toolchains worker. Runs INSIDE its own sandbox (see `linux-studio --toolchains-worker`):
  * network: ONLY the official download sites in official-sites.json, through the Linux Studio proxy
  * files:   ONLY /toolchains (read-write); publisher keys at /run/linux-studio/keys (read-only)

Every install: download -> SHA-256 must match the publisher's checksum -> the publisher's signature must be
good (when the publisher signs) -> unpack safely into a staging folder -> renamed into place only if all succeed.

Messages: one JSON object per line on stdin; replies one per line on stdout.
  {"op":"versions","tool":T}            -> {"op":"versions","tool":T,"items":[{"version","label"}]}
  {"op":"install","tool":T,"version":V} -> {"op":"progress",...,"stage","pct"} ... {"op":"done"} | {"op":"error","message"}
  {"op":"installed"}                    -> {"op":"installed","items":[{"tool","version","current"}]}
  {"op":"use"|"remove","tool":T,"version":V} -> {"op":"installed",...}
  {"op":"bundled"}                      -> {"op":"bundled","items":[{"name","version"}]}
Standard library only.
"""
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import threading
import queue
import tomllib
import urllib.parse
import urllib.request

ROOT = "/toolchains"
STAGING = os.path.join(ROOT, ".staging")
KEYS = "/run/linux-studio/keys"
TOOLS = ("python", "node", "go", "rust", "java", "cmake")
MAX_DOWNLOAD = 1536 * 1024 * 1024        # 1.5 GB per file
MAX_UNPACKED = 4 * 1024 * 1024 * 1024    # 4 GB unpacked
MAX_SMALL = 8 * 1024 * 1024              # version lists / checksum files
VERSION_RE = re.compile(r"^[0-9][0-9A-Za-z.+_-]{0,39}$")
UA = "linux-studio-toolchains"           # generic client name, nothing about the user
HTTP_TIMEOUT = 60
MAX_ENTRIES = 200_000                    # files in one archive (security review #6)
# Programs are always run by full path with a fixed PATH, so an installed toolchain can never replace
# gpgv, the shell or python3 for the worker (security review #1).
CLEAN_ENV = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": "/home/user"}

out_lock = threading.Lock()


class Fail(Exception):
    """An error with a plain-language message for the window."""


def send(**msg):
    with out_lock:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()


# ---------- network ----------
def _open(url):
    if not url.startswith("https://"):
        raise Fail("Refused a non-HTTPS address.")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        return urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)
    except Exception as e:  # noqa: BLE001 - reported as plain language
        raise Fail(f"Couldn't reach the download site ({urllib.parse.urlsplit(url).hostname}). "
                   "Check your internet connection and try again.") from e


def fetch_small(url):
    with _open(url) as r:
        data = r.read(MAX_SMALL + 1)
    if len(data) > MAX_SMALL:
        raise Fail("A version list was unexpectedly large and was refused.")
    return data


def fetch_json(url):
    try:
        return json.loads(fetch_small(url))
    except ValueError as e:
        raise Fail("The download site sent an unreadable version list.") from e


def download(url, path, progress):
    h = hashlib.sha256()
    with _open(url) as r, open(path, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        if total > MAX_DOWNLOAD:
            raise Fail("The download is larger than Linux Studio allows (1.5 GB).")
        done, last = 0, -1
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            done += len(chunk)
            if done > MAX_DOWNLOAD:
                raise Fail("The download is larger than Linux Studio allows (1.5 GB).")
            h.update(chunk)
            f.write(chunk)
            if total:
                pct = int(done * 100 / total)
                if pct != last:
                    last = pct
                    progress("downloading", pct)
    return h.hexdigest()


# ---------- verification ----------
def checksum_from_file(text, filename):
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].lstrip("*") == filename and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            return parts[0]
    raise Fail("The publisher's checksum list doesn't include this file, so it wasn't installed.")


def allowed_signers(keyring):
    with open(os.path.join(KEYS, "allowed-signers.json"), encoding="utf-8") as f:
        return set(json.load(f).get(keyring, []))


def verify_signature(keyring, sig_path, data_path):
    """Publisher signature check with gpgv against our stored key. Raises Fail unless the signature is valid
    AND was made by one of the currently valid signing keys listed in allowed-signers.json (gpgv alone
    ignores key expiry and accepts any key in the keyring; security review #3)."""
    bad = Fail("The publisher's signature didn't match, so the download was deleted and nothing was installed.")
    result = subprocess.run(["/usr/bin/gpgv", "--status-fd", "1", "--keyring", os.path.join(KEYS, keyring),
                             sig_path, data_path], capture_output=True, text=True, timeout=120, env=CLEAN_ENV)
    if result.returncode != 0:
        raise bad
    lines = [ln.split() for ln in result.stdout.splitlines() if ln.startswith("[GNUPG:] ")]
    if any(ln[1] in ("BADSIG", "ERRSIG", "EXPSIG", "EXPKEYSIG", "REVKEYSIG", "NO_PUBKEY") for ln in lines):
        raise bad
    valid = [ln for ln in lines if ln[1] == "VALIDSIG"]
    if len(valid) != 1 or valid[0][2].upper() not in allowed_signers(keyring):
        raise bad


def require_sha(actual, expected):
    if not expected or actual.lower() != expected.lower():
        raise Fail("The download didn't match the publisher's checksum, so it was deleted and nothing was installed.")


# ---------- safe unpacking ----------
def safe_extract(archive, dest):
    """Unpack with Python's 'data' filter: no absolute paths, no '..', no links leaving dest, no device files,
    no setuid bits. Also refuses archives that would unpack to more than MAX_UNPACKED."""
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        if len(members) > MAX_ENTRIES:
            raise Fail("The download contained too many files, so it was refused.")
        for m in members:   # official archives never contain these; treat any as tampering (stricter than the filter)
            if m.name.startswith("/") or ".." in m.name.replace("\\", "/").split("/"):
                raise Fail("The download contained unsafe file paths, so it was refused.")
        if sum(m.size for m in members if m.isfile()) > MAX_UNPACKED:
            raise Fail("The download would unpack to more than 4 GB, so it was refused.")
        try:
            tar.extractall(dest, filter="data")
        except (tarfile.FilterError, OSError) as e:
            raise Fail("The download contained unsafe file paths, so it was refused.") from e


def single_top_dir(path):
    entries = [e for e in os.listdir(path) if not e.startswith(".")]
    if len(entries) == 1 and os.path.isdir(os.path.join(path, entries[0])) \
            and not os.path.islink(os.path.join(path, entries[0])):
        return os.path.join(path, entries[0])
    return path


# ---------- publishers ----------
def node_versions():
    data = fetch_json("https://nodejs.org/dist/index.json")
    items, majors = [], set()
    for r in data:
        if "linux-x64" not in r.get("files", []) or "-" in r["version"]:   # skip pre-releases (alpha, rc, ...)
            continue
        major = r["version"].lstrip("v").split(".")[0]
        if major in majors:
            continue
        if not items:                                  # newest release of all
            items.append({"version": r["version"].lstrip("v"), "label": f"LTS ({r['lts']})" if r.get("lts") else "Current"})
            majors.add(major)
        elif r.get("lts"):
            items.append({"version": r["version"].lstrip("v"), "label": f"LTS ({r['lts']})"})
            majors.add(major)
        if len(items) >= 4:
            break
    return items


def node_install(version, work, progress):
    base = f"https://nodejs.org/dist/v{version}/"
    name = f"node-v{version}-linux-x64.tar.xz"
    sums, sig = os.path.join(work, "SHASUMS256.txt"), os.path.join(work, "SHASUMS256.txt.sig")
    with open(sums, "wb") as f:
        f.write(fetch_small(base + "SHASUMS256.txt"))
    with open(sig, "wb") as f:
        f.write(fetch_small(base + "SHASUMS256.txt.sig"))
    progress("verifying", None)
    verify_signature("node.gpg", sig, sums)            # checksum list signed by a Node.js releaser
    expected = checksum_from_file(open(sums).read(), name)
    archive = os.path.join(work, name)
    require_sha(download(base + name, archive, progress), expected)
    return archive


def go_versions():
    data = fetch_json("https://go.dev/dl/?mode=json")
    return [{"version": r["version"].removeprefix("go"), "label": "Stable"} for r in data if r.get("stable")][:4]


def go_install(version, work, progress):
    data = fetch_json("https://go.dev/dl/?mode=json&include=all")
    rel = next((r for r in data if r.get("version") == f"go{version}"), None)
    f = rel and next((x for x in rel.get("files", []) if x.get("os") == "linux" and x.get("arch") == "amd64"
                      and x.get("kind") == "archive"), None)
    if not f or not re.fullmatch(r"go[0-9A-Za-z.]+\.linux-amd64\.tar\.gz", f.get("filename", "")):
        raise Fail("Go doesn't list a Linux download for this version.")
    archive = os.path.join(work, f["filename"])
    require_sha(download("https://dl.google.com/go/" + f["filename"], archive, progress), f.get("sha256"))
    return archive


def rust_manifest(work=None):
    """The stable-channel list, signature-checked (security review #7) so an older release can't be passed off."""
    url = "https://static.rust-lang.org/dist/channel-rust-stable.toml"
    raw = fetch_small(url)
    tmp = work or os.path.join(STAGING, f"rust-manifest-{secrets.token_hex(4)}")
    os.makedirs(tmp, exist_ok=True)
    try:
        with open(os.path.join(tmp, "channel.toml"), "wb") as f:
            f.write(raw)
        with open(os.path.join(tmp, "channel.toml.asc"), "wb") as f:
            f.write(fetch_small(url + ".asc"))
        verify_signature("rust.gpg", os.path.join(tmp, "channel.toml.asc"), os.path.join(tmp, "channel.toml"))
    finally:
        if work is None:
            shutil.rmtree(tmp, ignore_errors=True)
    data = tomllib.loads(raw.decode())
    pkg = data["pkg"]["rust"]
    version = pkg["version"].split()[0]
    target = pkg["target"]["x86_64-unknown-linux-gnu"]
    return version, target


def rust_versions():
    version, target = rust_manifest()
    return [{"version": version, "label": "Stable"}] if target.get("available") else []


def rust_install(version, work, progress):
    latest, target = rust_manifest(work)
    if version != latest:
        raise Fail("Only the newest stable Rust can be installed. Refresh the list and try again.")
    url = target["xz_url"]
    if not url.startswith("https://static.rust-lang.org/dist/"):
        raise Fail("Rust's download address looked wrong, so it was refused.")
    archive = os.path.join(work, os.path.basename(url))
    require_sha(download(url, archive, progress), target.get("xz_hash"))
    progress("verifying", None)
    sig = archive + ".asc"
    with open(sig, "wb") as f:
        f.write(fetch_small(url + ".asc"))
    verify_signature("rust.gpg", sig, archive)
    return archive


def java_versions():
    info = fetch_json("https://api.adoptium.net/v3/info/available_releases")
    features = sorted(info.get("available_lts_releases", [])[-3:], reverse=True)
    items = []
    for feature in features:
        assets = fetch_json(f"https://api.adoptium.net/v3/assets/latest/{int(feature)}/hotspot"
                            "?architecture=x64&image_type=jdk&os=linux&vendor=eclipse")
        if assets:
            items.append({"version": assets[0]["release_name"].removeprefix("jdk-"), "label": "LTS"})
    return items


def java_install(version, work, progress):
    feature = int(version.split(".")[0].split("+")[0])
    assets = fetch_json(f"https://api.adoptium.net/v3/assets/latest/{feature}/hotspot"
                        "?architecture=x64&image_type=jdk&os=linux&vendor=eclipse")
    asset = next((a for a in assets if a.get("release_name") == f"jdk-{version}"), None)
    if not asset:
        raise Fail("That Java version is no longer offered. Refresh the list and try again.")
    pkg = asset["binary"]["package"]
    if not re.fullmatch(r"OpenJDK[0-9A-Za-z._-]+\.tar\.gz", pkg.get("name", "")):
        raise Fail("Java's download looked wrong, so it was refused.")
    archive = os.path.join(work, pkg["name"])
    require_sha(download(pkg["link"], archive, progress), pkg.get("checksum"))
    progress("verifying", None)
    sig = archive + ".sig"
    with open(sig, "wb") as f:
        f.write(fetch_small(pkg["signature_link"]))
    verify_signature("java.gpg", sig, archive)
    return archive


def cmake_versions():
    rels = fetch_json("https://api.github.com/repos/Kitware/CMake/releases?per_page=10")
    return [{"version": r["tag_name"].lstrip("v"), "label": "Latest" if i == 0 else "Release"}
            for i, r in enumerate([r for r in rels if not r.get("prerelease") and not r.get("draft")][:3])]


def cmake_install(version, work, progress):
    base = f"https://github.com/Kitware/CMake/releases/download/v{version}/"
    sums_name = f"cmake-{version}-SHA-256.txt"
    sums, sig = os.path.join(work, sums_name), os.path.join(work, sums_name + ".asc")
    with open(sums, "wb") as f:
        f.write(fetch_small(base + sums_name))
    with open(sig, "wb") as f:
        f.write(fetch_small(base + sums_name + ".asc"))
    progress("verifying", None)
    verify_signature("cmake.gpg", sig, sums)
    name = f"cmake-{version}-linux-x86_64.tar.gz"
    expected = checksum_from_file(open(sums).read(), name)
    archive = os.path.join(work, name)
    require_sha(download(base + name, archive, progress), expected)
    return archive


PBS = "https://github.com/astral-sh/python-build-standalone/releases/download/"
PBS_RE = r"cpython-(3\.\d+\.\d+)\+{tag}-x86_64-unknown-linux-gnu-install_only\.tar\.gz"


def python_release():
    latest = fetch_json("https://raw.githubusercontent.com/astral-sh/python-build-standalone/latest-release/latest-release.json")
    tag = str(latest.get("tag", ""))
    if not re.fullmatch(r"\d{8}", tag):
        raise Fail("python-build-standalone sent an unexpected release name.")
    sums = fetch_small(f"{PBS}{tag}/SHA256SUMS").decode()
    found = {}
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2:
            m = re.fullmatch(PBS_RE.format(tag=tag), parts[1])
            if m:
                found[m.group(1)] = (parts[1], parts[0])
    return tag, found


def python_versions():
    _, found = python_release()
    best = {}
    for v in found:
        minor = ".".join(v.split(".")[:2])
        if minor not in best or tuple(map(int, v.split("."))) > tuple(map(int, best[minor].split("."))):
            best[minor] = v
    order = sorted(best.values(), key=lambda v: tuple(map(int, v.split("."))), reverse=True)
    return [{"version": v, "label": "Latest" if i == 0 else "Supported"} for i, v in enumerate(order[:4])]


def python_install(version, work, progress):
    tag, found = python_release()
    if version not in found:
        raise Fail("That Python version is no longer offered. Refresh the list and try again.")
    name, expected = found[version]
    archive = os.path.join(work, name)
    require_sha(download(PBS + tag + "/" + urllib.parse.quote(name), archive, progress), expected)
    return archive


PUBLISHERS = {
    "node": (node_versions, node_install), "go": (go_versions, go_install), "rust": (rust_versions, rust_install),
    "java": (java_versions, java_install), "cmake": (cmake_versions, cmake_install),
    "python": (python_versions, python_install),
}


# ---------- install / use / remove ----------
def check_args(tool, version=None):
    if tool not in TOOLS:
        raise Fail("Unknown toolchain.")
    if version is not None and (not VERSION_RE.fullmatch(version) or ".." in version):
        raise Fail("Unusual version name refused.")


def tool_dir(tool):
    d = os.path.join(ROOT, tool)
    if os.path.islink(d):
        raise Fail("The toolchains folder looks tampered with; nothing was changed.")
    os.makedirs(d, exist_ok=True)
    return d


def install(tool, version):
    check_args(tool, version)
    final = os.path.join(tool_dir(tool), version)
    if os.path.lexists(final):
        raise Fail("That version is already installed.")
    os.makedirs(STAGING, exist_ok=True)
    work = os.path.join(STAGING, f"{tool}-{version}-{secrets.token_hex(4)}")
    os.makedirs(work)

    def progress(stage, pct):
        send(op="progress", tool=tool, version=version, stage=stage, pct=pct)
    try:
        progress("downloading", 0)
        archive = PUBLISHERS[tool][1](version, work, progress)
        progress("unpacking", None)
        unpacked = os.path.join(work, "unpacked")
        os.makedirs(unpacked)
        safe_extract(archive, unpacked)
        os.unlink(archive)
        top = single_top_dir(unpacked)
        if tool == "rust":                    # Rust's standalone installer copies files into a prefix
            prefix = os.path.join(work, "prefix")
            r = subprocess.run(["/bin/sh", os.path.join(top, "install.sh"), f"--prefix={prefix}", "--disable-ldconfig",
                                "--without=rust-docs"], capture_output=True, text=True, timeout=1800, cwd=top,
                               env=CLEAN_ENV)
            if r.returncode != 0:
                raise Fail("Rust's installer failed, so nothing was installed.")
            top = prefix
        if not os.path.isdir(os.path.join(top, "bin")):
            raise Fail("The download didn't have the expected layout, so nothing was installed.")
        os.rename(top, final)                 # appears only when everything succeeded
        send(op="done", tool=tool, version=version)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def installed():
    items = []
    for tool in TOOLS:
        d = os.path.join(ROOT, tool)
        if not os.path.isdir(d) or os.path.islink(d):
            continue
        current = os.path.join(d, "current")
        target = os.readlink(current) if os.path.islink(current) else None
        for v in sorted(os.listdir(d)):
            p = os.path.join(d, v)
            if v != "current" and VERSION_RE.fullmatch(v) and os.path.isdir(p) and not os.path.islink(p):
                items.append({"tool": tool, "version": v, "current": v == target})
    return items


def use(tool, version):
    check_args(tool, version)
    d = tool_dir(tool)
    target = os.path.join(d, version)
    if not os.path.isdir(target) or os.path.islink(target):
        raise Fail("That version isn't installed.")
    tmp = os.path.join(d, f".current-{secrets.token_hex(4)}")
    os.symlink(version, tmp)                  # relative link inside the tool's folder
    os.replace(tmp, os.path.join(d, "current"))


def remove(tool, version):
    check_args(tool, version)
    d = tool_dir(tool)
    target = os.path.join(d, version)
    if not os.path.isdir(target) or os.path.islink(target):
        raise Fail("That version isn't installed.")
    current = os.path.join(d, "current")
    if os.path.islink(current) and os.readlink(current) == version:
        os.unlink(current)
    shutil.rmtree(target)


def bundled():
    checks = [("Python", ["/usr/bin/python3", "--version"], r"Python (\S+)"), ("Node.js", ["/usr/bin/node", "--version"], r"v(\S+)"),
              ("GCC", ["/usr/bin/gcc", "-dumpfullversion"], r"(\S+)"), ("Clang", ["/usr/bin/clang", "--version"], r"version (\S+)"),
              ("CMake", ["/usr/bin/cmake", "--version"], r"version (\S+)"), ("Git", ["/usr/bin/git", "--version"], r"version (\S+)")]
    items = []
    for name, cmd, pattern in checks:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=CLEAN_ENV).stdout
            m = re.search(pattern, out)
            if m:
                items.append({"name": name, "version": m.group(1)})
        except (OSError, subprocess.TimeoutExpired):
            pass
    return items


# ---------- message loop ----------
def handle(msg):
    op, tool, version = msg.get("op"), msg.get("tool"), msg.get("version")
    try:
        if op == "versions":
            check_args(tool)
            send(op="versions", tool=tool, items=PUBLISHERS[tool][0]())
        elif op == "install":
            install(tool, version)
            send(op="installed", items=installed())
        elif op == "installed":
            send(op="installed", items=installed())
        elif op == "use":
            use(tool, version)
            send(op="installed", items=installed())
        elif op == "remove":
            remove(tool, version)
            send(op="installed", items=installed())
        elif op == "bundled":
            send(op="bundled", items=bundled())
    except Fail as e:
        send(op="error", tool=tool or "", version=version, message=str(e))
    except Exception:  # noqa: BLE001 - never show internal details
        send(op="error", tool=tool or "", version=version, message="Something unexpected went wrong. Nothing was changed.")


def main():
    os.makedirs(STAGING, exist_ok=True)
    shutil.rmtree(STAGING, ignore_errors=True)   # leftovers from an interrupted install
    # Changes (install / use / remove) run one at a time, in the order asked; look-ups run alongside.
    changes = queue.Queue()

    def run_changes():
        while True:
            msg = changes.get()
            if msg is None:
                return
            handle(msg)
    changer = threading.Thread(target=run_changes, daemon=True)
    changer.start()
    lookups = []
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if not isinstance(msg, dict):
            continue
        if msg.get("op") in ("install", "use", "remove"):
            changes.put(msg)
        else:
            t = threading.Thread(target=handle, args=(msg,), daemon=True)
            t.start()
            lookups.append(t)
    # Input closed (e.g. scripted use): finish work already asked for. When the window closes, the launcher
    # stops this sandbox anyway, and any half-finished install is only in .staging (cleared next start).
    changes.put(None)
    changer.join()
    for t in lookups:
        t.join()


if __name__ == "__main__":
    main()
