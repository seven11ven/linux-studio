#!/usr/bin/python3
"""Linux Studio "N websites are waiting" notice (network inbox, approved mockup screen 8). Runs on your real desktop,
outside the sandbox, started by the proxy when a new site waits in the network inbox. One notice at a time: the
proxy updates its count in place instead of opening more windows.

It never takes the keyboard (so typing in the editor can't answer it), stays on top on X11, and its buttons are locked
for the first second. It can't answer requests itself; "Open inbox" asks the proxy to show the inbox window.

Usage: waiting_notice.py <count>
stdin  (from the proxy): "count N" lines; "count 0" closes the notice.
stdout (to the proxy):   "open" (Open inbox) or "later" (hide until a new site arrives).
Needs: python3-gi and gir1.2-gtk-4.0.
"""
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from studio_theme import apply_theme  # noqa: E402
from window_attention import demand_attention, no_keyboard_focus  # noqa: E402

BUTTON_DELAY_MS = 1000


def text_for(n):
    return f"<b>{n} website{'s are' if n != 1 else ' is'}</b> waiting for your approval."


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    count = int(sys.argv[1])
    app = Gtk.Application(application_id="io.github.seven11ven.linuxstudio.WaitingNotice",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)

    def say(word):
        try:
            print(word, flush=True)
        except OSError:
            pass

    def on_activate(application):
        win = Gtk.ApplicationWindow(application=application, title="Linux Studio · Network requests")
        win.set_default_size(420, -1)
        win.set_resizable(False)
        apply_theme(win)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(18)
        win.set_child(box)
        pill = Gtk.Label(label="Waiting for you", halign=Gtk.Align.START)
        pill.add_css_class("ls-pill-warn")
        box.append(pill)
        label = Gtk.Label(xalign=0, wrap=True, use_markup=True, label=text_for(count))
        box.append(label)
        hint = Gtk.Label(xalign=0, wrap=True, label="Until you decide, these sites are refused. Requests you don't "
                                                    "answer expire after 10 minutes.")
        hint.add_css_class("ls-muted")
        box.append(hint)
        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        later = Gtk.Button(label="Later", sensitive=False)
        opener = Gtk.Button(label="Open inbox", sensitive=False)
        opener.add_css_class("ls-primary")
        actions.append(later)
        actions.append(opener)
        box.append(actions)

        def done(word):
            say(word)
            win.close()
        later.connect("clicked", lambda _b: done("later"))
        opener.connect("clicked", lambda _b: done("open"))
        GLib.timeout_add(BUTTON_DELAY_MS, lambda: [b.set_sensitive(True) for b in (later, opener)] and False)

        def update(line):
            parts = line.split()
            if len(parts) == 2 and parts[0] == "count" and parts[1].isdigit():
                n = int(parts[1])
                if n == 0:
                    win.close()
                else:
                    label.set_markup(text_for(n))
            return False

        def read_stdin():
            for line in sys.stdin:
                GLib.idle_add(update, line.strip())
            GLib.idle_add(lambda: win.close() or False)      # the proxy went away
        threading.Thread(target=read_stdin, daemon=True).start()

        # On top (not hidden behind Linux Studio), but never taking the keyboard.
        win.connect("realize", lambda w: no_keyboard_focus(w))
        win.connect("map", lambda w: no_keyboard_focus(w))
        win.connect("map", lambda w: GLib.timeout_add(100, lambda: demand_attention(w, urgent=False) or False))
        win.present()

    app.connect("activate", on_activate)
    app.run([])
    return 0


if __name__ == "__main__":
    sys.exit(main())
