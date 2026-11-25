#!/usr/bin/python3
"""Linux Studio Toolchains explorer (mockup screen 4). Runs on your real desktop, outside the sandbox.
Opened with:  linux-studio --toolchains

The window itself never touches the internet or the toolchains folder. It starts a separate, sandboxed
"worker" (src/toolchains/worker.py) that can reach ONLY the official download sites and write ONLY to the
toolchains folder. When you close this window, the worker and its network connection stop.

Messages to and from the worker are single lines of JSON (see worker.py for the list).
Usage: explorer.py -- <command that starts the worker>
Needs: python3-gi and gir1.2-gtk-4.0.
"""
import json
import os
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from studio_theme import apply_theme  # noqa: E402

CATEGORIES = [
    ("installed", "Installed", None, None),
    ("python", "Python", ["python"], "Source: python-build-standalone (Astral, GitHub) · SHA-256 checked (the publisher doesn't sign these)"),
    ("node", "Node.js", ["node"], "Source: nodejs.org · SHA-256 and signature checked"),
    ("c", "C / C++", ["cmake"], "Source: CMake (Kitware, GitHub) · SHA-256 and signature checked. GCC and Clang are bundled."),
    ("more", "Rust, Go, Java", ["rust", "go", "java"],
     "Sources: static.rust-lang.org · go.dev · adoptium.net · Rust and Java: SHA-256 and signature checked. Go: SHA-256 only (Go doesn't sign its downloads)."),
]
TOOL_NAMES = {"python": "Python", "node": "Node.js", "cmake": "CMake", "rust": "Rust", "go": "Go", "java": "Java (Temurin)"}
STAGES = {"downloading": "Downloading", "verifying": "Verifying", "unpacking": "Installing"}


class Worker:
    """Runs the sandboxed worker and passes messages back to the window on the GTK main thread."""

    def __init__(self, cmd, on_message):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, bufsize=1)
        self.on_message = on_message
        self.lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        while True:
            line = self.proc.stdout.readline(1_000_000)        # cap each message (security review #6)
            if not line:
                break
            if not line.endswith("\n"):                       # over-long message: drop the rest of it
                while True:
                    rest = self.proc.stdout.readline(1_000_000)
                    if not rest or rest.endswith("\n"):
                        break
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            GLib.idle_add(self.on_message, msg)
        GLib.idle_add(self.on_message, {"op": "worker-ended"})

    def send(self, **msg):
        with self.lock:
            try:
                self.proc.stdin.write(json.dumps(msg) + "\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def stop(self):
        try:
            self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(5)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()


class ExplorerWindow(Gtk.ApplicationWindow):
    def __init__(self, app, worker_cmd):
        super().__init__(application=app, title="Linux Studio · Toolchains")
        self.set_default_size(820, 520)
        apply_theme(self)
        self.versions = {}        # tool -> list of version dicts
        self.installed = []       # list of dicts {tool, version, current}
        self.bundled = []         # list of dicts {name, version}
        self.busy = {}            # (tool, version) -> stage text
        self.errors = {}          # (tool, version) -> message
        self.category = "installed"

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(outer)
        self.banner = Gtk.Label(xalign=0, wrap=True,
                                label="● Connecting to official download sites only. The connection closes when you close this window.")
        self.banner.add_css_class("ls-banner")
        outer.append(self.banner)

        body = Gtk.Box(vexpand=True)
        outer.append(body)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        side.add_css_class("ls-side")
        self.side_buttons = {}
        for key, label, _, _ in CATEGORIES:
            b = Gtk.ToggleButton(active=(key == "installed"))
            b.set_child(Gtk.Label(label=label, xalign=0))
            b.add_css_class("ls-side-item")
            b.connect("toggled", self.on_category, key)
            side.append(b)
            self.side_buttons[key] = b
        body.append(side)

        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for m in ("top", "bottom", "start", "end"):
            getattr(self.main, f"set_margin_{m}")(16)
        scroller.set_child(self.main)
        body.append(scroller)

        self.worker = Worker(worker_cmd, self.on_message)
        self.connect("close-request", self.on_close)
        self.worker.send(op="installed")
        self.worker.send(op="bundled")
        self.render()

    # ---------- worker messages ----------
    def on_message(self, msg):
        op = msg.get("op")
        if op != "worker-ended" and not getattr(self, "_connected", False):
            self._connected = True
            self.banner.set_text("● Connected to official download sites only. The connection closes when you close this window.")
        if op == "versions":
            self.versions[msg["tool"]] = msg.get("items", [])
            self.errors.pop((msg["tool"], "*"), None)
        elif op == "installed":
            self.installed = msg.get("items", [])
        elif op == "bundled":
            self.bundled = msg.get("items", [])
        elif op == "progress":
            pct = msg.get("pct")
            stage = STAGES.get(msg.get("stage"), msg.get("stage", ""))
            self.busy[(msg["tool"], msg["version"])] = f"{stage} {pct}%" if pct is not None else stage
        elif op == "done":
            self.busy.pop((msg["tool"], msg["version"]), None)
            self.worker.send(op="installed")
        elif op == "error":
            key = (msg.get("tool", ""), msg.get("version") or "*")
            self.busy.pop(key, None)
            self.errors[key] = msg.get("message", "Something went wrong.")
        elif op == "worker-ended":
            self.banner.set_text("○ Disconnected. Close and reopen this window to try again.")
        self.render()
        return False

    # ---------- UI ----------
    def on_category(self, button, key):
        if not button.get_active():
            if self.category == key:
                button.set_active(True)
            return
        self.category = key
        for k, b in self.side_buttons.items():
            if k != key and b.get_active():
                b.set_active(False)
        for _, _, tools, _ in CATEGORIES:
            pass
        tools = next(c[2] for c in CATEGORIES if c[0] == key)
        for tool in tools or []:
            if tool not in self.versions:
                self.worker.send(op="versions", tool=tool)
        self.render()

    def clear(self):
        child = self.main.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.main.remove(child)
            child = nxt

    def heading(self, title, subtitle):
        t = Gtk.Label(label=title, xalign=0)
        t.add_css_class("ls-title")
        self.main.append(t)
        if subtitle:
            s = Gtk.Label(label=subtitle, xalign=0, wrap=True)
            s.add_css_class("ls-muted")
            self.main.append(s)

    def table(self, headers):
        grid = Gtk.Grid(column_spacing=18, row_spacing=6)
        for col, h in enumerate(headers):
            lab = Gtk.Label(label=h, xalign=0)
            lab.add_css_class("ls-header")
            grid.attach(lab, col, 0, 1, 1)
        self.main.append(grid)
        return grid

    def pill(self, text, kind=""):
        p = Gtk.Label(label=text, halign=Gtk.Align.START, valign=Gtk.Align.CENTER)
        p.add_css_class({"ok": "ls-pill-ok", "bad": "ls-pill-bad", "warn": "ls-pill-warn"}.get(kind, "ls-pill"))
        return p

    def render(self):
        self.clear()
        cat = next(c for c in CATEGORIES if c[0] == self.category)
        if self.category == "installed":
            self.render_installed()
        else:
            self.heading(cat[1], cat[3])
            for tool in cat[2]:
                self.render_tool(tool, show_name=len(cat[2]) > 1)

    def render_installed(self):
        self.heading("Installed", "Bundled toolchains ship with Linux Studio and work offline. Extra versions are below.")
        g = self.table(["NAME", "VERSION", "STATUS", ""])
        row = 1
        for item in self.bundled:
            g.attach(Gtk.Label(label=item["name"], xalign=0), 0, row, 1, 1)
            v = Gtk.Label(label=item["version"], xalign=0)
            v.add_css_class("ls-mono")
            g.attach(v, 1, row, 1, 1)
            g.attach(self.pill("Bundled", "ok"), 2, row, 1, 1)
            row += 1
        for item in sorted(self.installed, key=lambda i: (i["tool"], i["version"])):
            tool, version = item["tool"], item["version"]
            g.attach(Gtk.Label(label=TOOL_NAMES.get(tool, tool), xalign=0), 0, row, 1, 1)
            v = Gtk.Label(label=version, xalign=0)
            v.add_css_class("ls-mono")
            g.attach(v, 1, row, 1, 1)
            g.attach(self.pill("In use" if item.get("current") else "Installed", "ok" if item.get("current") else ""),
                     2, row, 1, 1)
            btns = Gtk.Box(spacing=6, halign=Gtk.Align.END, valign=Gtk.Align.CENTER, hexpand=True)
            if not item.get("current"):
                use = Gtk.Button(label="Use this version")
                use.connect("clicked", lambda _b, t=tool, v=version: self.worker.send(op="use", tool=t, version=v))
                btns.append(use)
            rm = Gtk.Button(label="Remove")
            rm.add_css_class("ls-danger")
            rm.connect("clicked", lambda _b, t=tool, v=version: self.worker.send(op="remove", tool=t, version=v))
            btns.append(rm)
            g.attach(btns, 3, row, 1, 1)
            row += 1
        if not self.installed:
            note = Gtk.Label(label="No extra toolchains yet. Pick a language on the left to install one.", xalign=0)
            note.add_css_class("ls-muted")
            self.main.append(note)
        else:
            note = Gtk.Label(xalign=0, wrap=True, label="“Use this version” decides which version your terminal runs. "
                             "Restart the editor to pick up changes.")
            note.add_css_class("ls-muted")
            self.main.append(note)

    def render_tool(self, tool, show_name):
        if show_name:
            sub = Gtk.Label(label=TOOL_NAMES[tool], xalign=0)
            sub.add_css_class("ls-subtitle")
            self.main.append(sub)
        err = self.errors.get((tool, "*"))
        if err:
            e = Gtk.Label(label=err, xalign=0, wrap=True)
            e.add_css_class("ls-error")
            self.main.append(e)
        items = self.versions.get(tool)
        if items is None:
            self.main.append(Gtk.Label(label="Loading versions…", xalign=0))
            return
        installed = {(i["tool"], i["version"]) for i in self.installed}
        g = self.table(["NAME", "VERSION", "STATUS", ""])
        for row, item in enumerate(items, start=1):
            version = item["version"]
            key = (tool, version)
            g.attach(Gtk.Label(label=TOOL_NAMES[tool], xalign=0), 0, row, 1, 1)
            v = Gtk.Label(label=version, xalign=0)
            v.add_css_class("ls-mono")
            g.attach(v, 1, row, 1, 1)
            if key in installed:
                g.attach(self.pill("Installed", "ok"), 2, row, 1, 1)
            elif key in self.busy:
                g.attach(self.pill(self.busy[key], "warn"), 2, row, 1, 1)
            else:
                g.attach(self.pill(item.get("label", "")), 2, row, 1, 1)
                b = Gtk.Button(label="Install", halign=Gtk.Align.END, valign=Gtk.Align.CENTER, hexpand=True)
                b.add_css_class("ls-primary")
                b.connect("clicked", self.on_install, tool, version)
                g.attach(b, 3, row, 1, 1)
            if key in self.errors:
                e = Gtk.Label(label=self.errors[key], xalign=0, wrap=True)
                e.add_css_class("ls-error")
                g.attach(e, 0, row + 1000, 4, 1)

    def on_install(self, _b, tool, version):
        self.errors.pop((tool, version), None)
        self.busy[(tool, version)] = "Starting"
        self.worker.send(op="install", tool=tool, version=version)
        self.render()

    def on_close(self, *_):
        self.worker.stop()
        return False


def main():
    if "--" not in sys.argv or sys.argv.index("--") == len(sys.argv) - 1:
        print("Usage: explorer.py -- <worker command>", file=sys.stderr)
        return 2
    worker_cmd = sys.argv[sys.argv.index("--") + 1:]
    app = Gtk.Application(application_id="io.github.seven11ven.linuxstudio.Toolchains",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.connect("activate", lambda a: ExplorerWindow(a, worker_cmd).present())
    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
