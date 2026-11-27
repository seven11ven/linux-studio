#!/usr/bin/python3
"""Linux Studio network inbox (approved mockup screen 8). Runs on your real desktop, outside the sandbox, started by
the proxy. Lists the websites that something inside Linux Studio asked to reach and that are waiting for your answer:
Deny, Allow once or Always allow for each, or Deny all. Code inside Linux Studio can't see or answer this window.

The buttons lock for a second whenever the list changes or the window is shown again, so a click aimed elsewhere can't
land on them. Requests expire after 10 minutes (the proxy removes them).

stdin  (from the proxy): one JSON line {"sites": [{"host", "since", "expires"}, ...]} per change, or "show".
stdout (to the proxy):   "deny HOST", "once HOST", "always HOST" or "denyall".
Needs: python3-gi and gir1.2-gtk-4.0.
"""
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from netpolicy import normalise_host  # noqa: E402
from studio_theme import apply_theme  # noqa: E402

BUTTON_DELAY_MS = 1000


class InboxWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Linux Studio · Network inbox")
        self.set_default_size(720, 420)
        apply_theme(self)
        self.sites = []
        self.buttons = []
        self.unlock_id = 0
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(outer, f"set_margin_{side}")(20)
        self.set_child(outer)
        top = Gtk.Box(spacing=8)
        title = Gtk.Label(label="Network inbox", xalign=0, hexpand=True)
        title.add_css_class("ls-title")
        self.deny_all = Gtk.Button(label="Deny all")
        self.deny_all.add_css_class("ls-danger")
        self.deny_all.connect("clicked", lambda _b: self.answer("denyall", None))
        top.append(title)
        top.append(self.deny_all)
        outer.append(top)
        hint = Gtk.Label(xalign=0, wrap=True, label=(
            "Something inside Linux Studio (an extension or a terminal tool) asked to connect to these sites. Each will "
            "see your public IP address, but not your username, computer name or files. Until you decide, they are "
            "refused; requests you don't answer expire after 10 minutes."))
        hint.add_css_class("ls-muted")
        outer.append(hint)
        self.grid = Gtk.Grid(column_spacing=16, row_spacing=6)
        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_child(self.grid)
        outer.append(scroller)
        self.connect("notify::is-active", lambda w, _p: w.is_active() and self.lock_buttons())
        GLib.timeout_add_seconds(30, self.tick)      # keep "expires in" current
        self.draw()

    # A second's lock whenever the list changes or the window comes forward again (clicks aimed elsewhere).
    def lock_buttons(self):
        for b in self.buttons + [self.deny_all]:
            b.set_sensitive(False)
        if self.unlock_id:
            GLib.source_remove(self.unlock_id)

        def unlock():
            self.unlock_id = 0
            for b in self.buttons:
                b.set_sensitive(True)
            self.deny_all.set_sensitive(bool(self.sites))
            return False
        self.unlock_id = GLib.timeout_add(BUTTON_DELAY_MS, unlock)

    def set_sites(self, sites):
        clean = []
        for x in sites if isinstance(sites, list) else []:
            host = normalise_host(x.get("host")) if isinstance(x, dict) else None
            if host:
                clean.append({"host": host, "since": int(x.get("since", 0)), "expires": int(x.get("expires", 0))})
        self.sites = clean
        self.draw()

    def tick(self):
        self.draw(lock=False)
        return True

    def draw(self, lock=True):
        child = self.grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt
        self.buttons = []
        for col, name in enumerate(("WEBSITE", "FIRST ASKED", "EXPIRES IN", "")):
            h = Gtk.Label(label=name, xalign=0)
            h.add_css_class("ls-header")
            self.grid.attach(h, col, 0, 1, 1)
        if not self.sites:
            empty = Gtk.Label(label="Nothing is waiting.", xalign=0)
            empty.add_css_class("ls-muted")
            self.grid.attach(empty, 0, 1, 4, 1)
        now = time.time()
        for row, x in enumerate(self.sites, start=1):
            # Never wrap the name: a line break could make a look-alike name read as a trusted one.
            name = Gtk.Label(label=x["host"], xalign=0, hexpand=True, selectable=True, wrap=False)
            name.add_css_class("ls-domain-small")
            first = Gtk.Label(label=time.strftime("%H:%M", time.localtime(x["since"])), xalign=0)
            mins = max(0, int((x["expires"] - now + 59) // 60))
            left = Gtk.Label(label=f"{mins} min", xalign=0)
            for w in (first, left):
                w.add_css_class("ls-muted")
            btns = Gtk.Box(spacing=6, halign=Gtk.Align.END)
            for label, verb, css in (("Deny", "deny", "ls-danger"), ("Allow once", "once", None),
                                     ("Always allow", "always", "ls-primary")):
                b = Gtk.Button(label=label)
                if css:
                    b.add_css_class(css)
                b.connect("clicked", lambda _b, v=verb, h=x["host"]: self.answer(v, h))
                btns.append(b)
                self.buttons.append(b)
            for col, w in enumerate((name, first, left, btns)):
                self.grid.attach(w, col, row, 1, 1)
        if lock:
            self.lock_buttons()
        else:
            self.deny_all.set_sensitive(bool(self.sites) and not self.unlock_id)

    def answer(self, verb, host):
        try:
            print(verb if host is None else f"{verb} {host}", flush=True)
        except OSError:
            return
        self.sites = [] if host is None else [x for x in self.sites if x["host"] != host]
        self.draw()


def main():
    app = Gtk.Application(application_id="io.github.seven11ven.linuxstudio.NetworkInbox",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)

    def on_activate(application):
        win = InboxWindow(application)

        def apply(line):
            if line == "show":
                win.present()
            else:
                try:
                    data = json.loads(line)
                except ValueError:
                    return False
                if isinstance(data, dict):
                    win.set_sites(data.get("sites"))
            return False

        def read_stdin():
            for line in sys.stdin:
                GLib.idle_add(apply, line.strip())
        threading.Thread(target=read_stdin, daemon=True).start()
        win.present()

    app.connect("activate", on_activate)
    app.run([])
    return 0


if __name__ == "__main__":
    sys.exit(main())
