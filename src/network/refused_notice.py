#!/usr/bin/python3
"""Linux Studio "Connection refused" notice (approved mockup, screen 2). Runs on your real desktop, outside the
sandbox, started by the proxy when something inside Linux Studio is refused WITHOUT a pop-up:

  blocked     you blocked the site (in Approved websites, or by choosing Deny)
  unanswered  an earlier pop-up for the site was closed or not answered, so it's refused until Linux Studio restarts

Shown at most once per site per session (the proxy keeps track), never takes keyboard focus, closes itself after
20 seconds, and its buttons are locked for the first second (like the approval pop-up).

Usage: refused_notice.py <site> blocked|unanswered
Exit code: 20 = Open Approved websites, 21 = Ask me now, 1 = dismissed / closed / timed out.
Needs: python3-gi and gir1.2-gtk-4.0.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from netpolicy import normalise_host  # noqa: E402
from studio_theme import apply_theme  # noqa: E402
from window_attention import demand_attention, no_keyboard_focus  # noqa: E402

OPEN_SITES, ASK_NOW, DISMISSED = 20, 21, 1
BUTTON_DELAY_MS = 1000
AUTO_CLOSE_S = 20


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in ("blocked", "unanswered"):
        print(__doc__, file=sys.stderr)
        return 2
    host = normalise_host(sys.argv[1])
    kind = sys.argv[2]
    if not host:
        return 2
    result = {"code": DISMISSED}
    app = Gtk.Application(application_id="io.github.seven11ven.linuxstudio.RefusedNotice",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)

    def on_activate(application):
        win = Gtk.ApplicationWindow(application=application, title="Linux Studio · Connection refused")
        win.set_default_size(440, -1)
        win.set_resizable(False)
        apply_theme(win)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(20)
        win.set_child(box)

        pill = Gtk.Label(label="Refused", halign=Gtk.Align.START)
        pill.add_css_class("ls-pill-bad")
        box.append(pill)
        intro = Gtk.Label(label="Linux Studio refused a connection to", xalign=0)
        box.append(intro)
        # Never wrap the name (a line break could make a look-alike name read as a trusted one).
        site = Gtk.Label(label=host, xalign=0, selectable=True, wrap=False)
        site.add_css_class("ls-domain")
        box.append(site)
        if kind == "blocked":
            why = "because you blocked this site."
            action_label, action_code = "Open Approved websites…", OPEN_SITES
        else:
            why = ("because the earlier question about it was closed or not answered. It won't ask again until "
                   "Linux Studio restarts.")
            action_label, action_code = "Ask me now", ASK_NOW
        box.append(Gtk.Label(label=why, xalign=0, wrap=True))

        def done(_b, c):
            result["code"] = c
            win.close()

        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        dismiss = Gtk.Button(label="Dismiss", sensitive=False)
        dismiss.connect("clicked", done, DISMISSED)
        act = Gtk.Button(label=action_label, sensitive=False)
        act.add_css_class("ls-primary")
        act.connect("clicked", done, action_code)
        actions.append(dismiss)
        actions.append(act)
        box.append(actions)
        hint = Gtk.Label(label=f"This closes by itself after {AUTO_CLOSE_S} seconds.", xalign=0)
        hint.add_css_class("ls-muted")
        box.append(hint)

        GLib.timeout_add(BUTTON_DELAY_MS, lambda: [b.set_sensitive(True) for b in (dismiss, act)] and False)
        GLib.timeout_add_seconds(AUTO_CLOSE_S, lambda: win.close() or False)
        # On top (so it isn't hidden behind Linux Studio) but without taking the keyboard.
        win.connect("realize", lambda w: no_keyboard_focus(w))
        win.connect("map", lambda w: no_keyboard_focus(w))   # GTK rewrites the hints when showing; set it again
        win.connect("map", lambda w: GLib.timeout_add(100, lambda: demand_attention(w, urgent=False) or False))
        win.present()

    app.connect("activate", on_activate)
    app.run([])
    return result["code"]


if __name__ == "__main__":
    sys.exit(main())
