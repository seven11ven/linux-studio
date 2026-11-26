#!/usr/bin/python3
"""Linux Studio "Approved websites" window (mockup screen 3). Runs on your real desktop, outside the sandbox.
Opened with:  linux-studio --network

Add a site, switch a site between Allowed and Blocked, remove it, or turn the whole network off.
Changes are saved to network.json at once, and a running Linux Studio picks them up immediately.

Usage: sites_manager.py --config PATH
Needs: python3-gi and gir1.2-gtk-4.0.
"""
import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from netpolicy import BUILTIN_BLOCKED, Store, normalise_host  # noqa: E402
from studio_theme import apply_theme  # noqa: E402


def friendly_time(stamp):
    if not stamp:
        return "Never"
    try:
        t = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return "Unknown"
    return t.strftime("%d %b %Y, %H:%M UTC")


class SitesWindow(Gtk.ApplicationWindow):
    def __init__(self, app, store):
        super().__init__(application=app, title="Linux Studio · Approved websites")
        self.store = store
        self.set_default_size(720, 480)
        apply_theme(self)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for side in ("top", "bottom", "start", "end"):
            getattr(outer, f"set_margin_{side}")(22)
        self.set_child(outer)

        top = Gtk.Box(spacing=8)
        title = Gtk.Label(label="Approved websites", xalign=0, hexpand=True)
        title.add_css_class("ls-title")
        self.net_label = Gtk.Label(xalign=1)
        top.append(title)
        top.append(self.net_label)
        outer.append(top)

        add_row = Gtk.Box(spacing=8)
        self.entry = Gtk.Entry(hexpand=True, placeholder_text="Add a site, e.g. registry.npmjs.org")
        self.entry.connect("activate", self.on_add)
        add_btn = Gtk.Button(label="Allow")
        add_btn.add_css_class("ls-primary")
        add_btn.connect("clicked", self.on_add)
        add_row.append(self.entry)
        add_row.append(add_btn)
        outer.append(add_row)
        self.error = Gtk.Label(xalign=0)
        self.error.add_css_class("ls-error")
        outer.append(self.error)

        self.grid = Gtk.Grid(column_spacing=16, row_spacing=4)
        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_child(self.grid)
        outer.append(scroller)

        bottom = Gtk.Box(spacing=8)
        note = Gtk.Label(label="Saved outside the sandbox. Extensions can't read or change this list.",
                         xalign=0, hexpand=True, wrap=True)
        note.add_css_class("ls-muted")
        self.toggle = Gtk.Button()
        self.toggle.connect("clicked", self.on_toggle)
        bottom.append(note)
        bottom.append(self.toggle)
        outer.append(bottom)

        self.refresh()
        GLib.timeout_add_seconds(3, self._poll)   # show new sites approved from pop-ups

    def _poll(self):
        self.refresh()
        return True

    def refresh(self):
        data = self.store.load()
        on = data["network_enabled"]
        self.net_label.set_text("● Network on: approved sites only" if on else "○ Network off: everything blocked")
        self.toggle.set_label("Turn network off" if on else "Turn network on")
        child = self.grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt
        for col, name in enumerate(("WEBSITE", "STATUS", "LAST USED", "")):
            h = Gtk.Label(label=name, xalign=0)
            h.add_css_class("ls-header")
            self.grid.attach(h, col, 0, 1, 1)
        sites = dict(data["sites"])
        for host in BUILTIN_BLOCKED:                 # built-in blocks the user hasn't overridden
            sites.setdefault(host, {"status": "blocked", "last_used": "", "builtin": True})
        sites = sorted(sites.items())
        if not sites:
            empty = Gtk.Label(label="No websites yet. They appear here when you approve or block one.", xalign=0)
            empty.add_css_class("ls-muted")
            self.grid.attach(empty, 0, 1, 4, 1)
        for row, (host, info) in enumerate(sites, start=1):
            name = Gtk.Label(label=host, xalign=0, hexpand=True, selectable=True)
            name.add_css_class("ls-domain-small")
            allowed = info["status"] == "allowed"
            builtin = info.get("builtin", False)
            if builtin:
                name.set_tooltip_text(BUILTIN_BLOCKED[host])
            pill = Gtk.Label(label="Allowed" if allowed else ("Blocked (built in)" if builtin else "Blocked"),
                             halign=Gtk.Align.START)
            pill.add_css_class("ls-pill-ok" if allowed else "ls-pill-bad")
            used = Gtk.Label(label=friendly_time(info["last_used"]), xalign=0)
            used.add_css_class("ls-muted")
            btns = Gtk.Box(spacing=6, halign=Gtk.Align.END)
            flip = Gtk.Button(label="Block" if allowed else "Allow")
            flip.connect("clicked", self.on_flip, host, "blocked" if allowed else "allowed")
            rm = Gtk.Button(label="Remove")
            rm.add_css_class("ls-danger")
            rm.connect("clicked", self.on_remove, host)
            btns.append(flip)
            if not builtin:                          # built-in entries can be allowed, not removed
                btns.append(rm)
            for col, w in enumerate((name, pill, used, btns)):
                self.grid.attach(w, col, row, 1, 1)

    def on_add(self, *_):
        host = normalise_host(self.entry.get_text())
        if not host:
            self.error.set_text("Enter a site name like example.com, without https:// or a path.")
            return
        self.error.set_text("")
        self.store.set_site(host, "allowed")
        self.entry.set_text("")
        self.refresh()

    def on_flip(self, _b, host, status):
        self.store.set_site(host, status)
        self.refresh()

    def on_remove(self, _b, host):
        self.store.remove_site(host)
        self.refresh()

    def on_toggle(self, *_):
        self.store.set_network(not self.store.load()["network_enabled"])
        self.refresh()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    store = Store(args.config)
    app = Gtk.Application(application_id="io.github.seven11ven.linuxstudio.Websites",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.connect("activate", lambda a: SitesWindow(a, store).present())
    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
