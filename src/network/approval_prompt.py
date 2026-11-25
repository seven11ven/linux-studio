#!/usr/bin/python3
"""Linux Studio network approval pop-up (mockup screen 2). Runs on your real desktop, outside the sandbox,
started by the proxy when something inside Linux Studio wants to reach a new website.

Usage: approval_prompt.py <site> <port>
Exit code: 10 = Deny (site saved as blocked), 11 = Allow once (this session), 12 = Always allow,
           13 = Block all new sites until Linux Studio restarts.
Closing the window or giving no answer refuses this site until Linux Studio restarts (the proxy handles the 60 s limit).
Needs: python3-gi and gir1.2-gtk-4.0.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from netpolicy import normalise_host  # noqa: E402
from studio_theme import apply_theme  # noqa: E402

DENY, ONCE, ALWAYS, BLOCK_NEW, CLOSED = 10, 11, 12, 13, 1
BUTTON_DELAY_MS = 1000   # buttons wait 1 s so a stray click or key press can't approve (security review #4)


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    host = normalise_host(sys.argv[1])
    port = sys.argv[2] if sys.argv[2].isdigit() else ""
    if not host or not port:
        return 2
    result = {"code": CLOSED}
    app = Gtk.Application(application_id="io.github.seven11ven.linuxstudio.NetworkPrompt",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)

    def on_activate(application):
        win = Gtk.ApplicationWindow(application=application, title="Linux Studio · Network request")
        win.set_default_size(480, -1)
        win.set_resizable(False)
        apply_theme(win)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(22)
        win.set_child(box)

        pill = Gtk.Label(label="Blocked until you decide", xalign=0, halign=Gtk.Align.START)
        pill.add_css_class("ls-pill-warn")
        box.append(pill)
        intro = Gtk.Label(label="Something inside Linux Studio wants to connect to", xalign=0)
        intro.add_css_class("ls-muted")
        box.append(intro)
        # Never wrap the name: a line break could make "github.com-login.evil.xyz" look like "github.com".
        site = Gtk.Label(label=host, xalign=0, selectable=True, wrap=False)
        site.add_css_class("ls-domain")
        box.append(site)

        grid = Gtk.Grid(column_spacing=14, row_spacing=6)
        rows = [("Port", f"{port} (HTTPS)"),
                ("Likely from", "An extension or a terminal tool (they share one connection)"),
                ("Time", time.strftime("%H:%M:%S"))]
        for i, (k, v) in enumerate(rows):
            kl = Gtk.Label(label=k, xalign=0)
            kl.add_css_class("ls-muted")
            vl = Gtk.Label(label=v, xalign=0, wrap=True)
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        box.append(grid)

        warn = Gtk.Label(xalign=0, wrap=True, label=(
            "This site will see your public IP address. It won't see your username, computer name, "
            "network devices or files."))
        warn.add_css_class("ls-note-warn")
        box.append(warn)

        hint = Gtk.Label(label="No answer within 60 seconds means Deny.", xalign=0)
        hint.add_css_class("ls-muted")
        box.append(hint)

        def done(_b, c):
            result["code"] = c
            win.close()

        buttons = []
        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        for label, code, css in (("Deny", DENY, "ls-danger"), ("Allow once", ONCE, None),
                                 ("Always allow", ALWAYS, "ls-primary")):
            b = Gtk.Button(label=label, sensitive=False)
            if css:
                b.add_css_class(css)
            b.connect("clicked", done, code)
            actions.append(b)
            buttons.append(b)
        box.append(actions)

        block = Gtk.Button(label="Block all new sites until Linux Studio restarts", sensitive=False,
                           halign=Gtk.Align.START)
        block.add_css_class("ls-link")
        block.connect("clicked", done, BLOCK_NEW)
        buttons.append(block)
        box.append(block)

        def enable():
            for b in buttons:
                b.set_sensitive(True)
            return False
        GLib.timeout_add(BUTTON_DELAY_MS, enable)
        # No default button: pressing Enter must not approve anything by accident.
        win.present()

    app.connect("activate", on_activate)
    app.run([])
    return result["code"]


if __name__ == "__main__":
    sys.exit(main())
